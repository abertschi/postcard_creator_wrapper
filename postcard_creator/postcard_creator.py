from requests_toolbelt.utils import dump
from PIL import Image
from io import BytesIO
from resizeimage import resizeimage
from time import gmtime, strftime

import logging
import datetime
import pkg_resources
import math
import os
import requests

LOGGING_TRACE_LVL = 5
logger = logging.getLogger('postcard_creator')
logging.addLevelName(LOGGING_TRACE_LVL, 'TRACE')
setattr(logger, 'trace', lambda *args: logger.log(LOGGING_TRACE_LVL, *args))


def _dump_request(response):
    data = dump.dump_all(response)
    try:
        logger.trace(data.decode())
    except Exception:
        data = str(data).replace('\\r\\n', '\r\n')
        logger.trace(data)


def _encode_text(text):
    return text.encode('ascii', 'xmlcharrefreplace').decode('utf-8')  # escape umlaute


class PostcardCreatorException(Exception):
    server_response = None


class Sender(object):
    def __init__(self, prename, lastname, street, zip_code, place, company='', country=''):
        self.prename = prename
        self.lastname = lastname
        self.street = street
        self.zip_code = zip_code
        self.place = place
        self.company = company
        self.country = country

    def is_valid(self):
        return all(field for field in [self.prename, self.lastname, self.street, self.zip_code, self.place])


class Recipient(object):
    def __init__(self, prename, lastname, street, zip_code, place, company='', company_addition='', salutation=''):
        self.salutation = salutation
        self.prename = prename
        self.lastname = lastname
        self.street = street
        self.zip_code = zip_code
        self.place = place
        self.company = company
        self.company_addition = company_addition

    def is_valid(self):
        return all(field for field in [self.prename, self.lastname, self.street, self.zip_code, self.place])

    def to_json(self):
        return {'recipientFields': [
            {'name': 'Salutation', 'addressField': 'SALUTATION'},
            {'name': 'Given Name', 'addressField': 'GIVEN_NAME'},
            {'name': 'Family Name', 'addressField': 'FAMILY_NAME'},
            {'name': 'Company', 'addressField': 'COMPANY'},
            {'name': 'Company', 'addressField': 'COMPANY_ADDITION'},
            {'name': 'Street', 'addressField': 'STREET'},
            {'name': 'Post Code', 'addressField': 'ZIP_CODE'},
            {'name': 'Place', 'addressField': 'PLACE'}],
            'recipients': [
                [self.salutation, self.prename,
                 self.lastname, self.company,
                 self.company_addition, self.street,
                 self.zip_code, self.place]]}


class Postcard(object):
    def __init__(self, sender, recipient, picture_stream, message=''):
        self.recipient = recipient
        self.message = message
        self.picture_stream = picture_stream
        self.sender = sender
        self.frontpage_layout = pkg_resources.resource_string(__name__, 'page_1.svg').decode('utf-8')
        self.backpage_layout = pkg_resources.resource_string(__name__, 'page_2.svg').decode('utf-8')

    def is_valid(self):
        return self.recipient is not None \
               and self.recipient.is_valid() \
               and self.sender is not None \
               and self.sender.is_valid()

    def validate(self):
        if self.recipient is None or not self.recipient.is_valid():
            raise PostcardCreatorException('Not all required attributes in recipient set')
        if self.recipient is None or not self.recipient.is_valid():
            raise PostcardCreatorException('Not all required attributes in sender set')

    def get_frontpage(self, asset_id):
        return self.frontpage_layout.replace('{asset_id}', str(asset_id))

    def get_backpage(self):
        svg = self.backpage_layout
        return svg \
            .replace('{first_name}', _encode_text(self.recipient.prename)) \
            .replace('{last_name}', _encode_text(self.recipient.lastname)) \
            .replace('{company}', _encode_text(self.recipient.company)) \
            .replace('{company_addition}', _encode_text(self.recipient.company_addition)) \
            .replace('{street}', _encode_text(self.recipient.street)) \
            .replace('{zip_code}', str(self.recipient.zip_code)) \
            .replace('{place}', _encode_text(self.recipient.place)) \
            .replace('{sender_company}', _encode_text(self.sender.company)) \
            .replace('{sender_name}', _encode_text(self.sender.prename) + ' ' + _encode_text(self.sender.lastname)) \
            .replace('{sender_address}', _encode_text(self.sender.street)) \
            .replace('{sender_zip_code}', str(self.sender.zip_code)) \
            .replace('{sender_place}', _encode_text(self.sender.place)) \
            .replace('{sender_country}', _encode_text(self.sender.country)) \
            .replace('{message}',
                     _encode_text(self.message))


def _send_free_card_defaults(func):
    def wrapped(*args, **kwargs):
        kwargs['image_target_width'] = kwargs.get('image_target_width') or 154
        kwargs['image_target_height'] = kwargs.get('image_target_height') or 111
        kwargs['image_quality_factor'] = kwargs.get('image_quality_factor') or 20
        kwargs['image_rotate'] = kwargs.get('image_rotate') or True
        kwargs['image_export'] = kwargs.get('image_export') or False
        return func(*args, **kwargs)

    return wrapped


class PostcardCreator(object):
    def __init__(self, token=None, _protocol='https://'):
        if token.token is None:
            raise PostcardCreatorException('No Token given')
        self.token = token
        self.protocol = _protocol
        self.host = '{}postcardcreator.post.ch/rest/2.2'.format(self.protocol)
        self._session = self._create_session()

    def _get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; wv) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Version/4.0 Chrome/52.0.2743.98 Mobile Safari/537.36',
            'Authorization': 'Bearer {}'.format(self.token.token)
        }

    def _create_session(self):
        return requests.Session()

    def _do_op(self, method, endpoint, **kwargs):
        url = self.host + endpoint
        if 'headers' not in kwargs or kwargs['headers'] is None:
            kwargs['headers'] = self._get_headers()

        logger.debug('{}: {}'.format(method, url))
        response = self._session.request(method, url, **kwargs)
        _dump_request(response)

        if response.status_code not in [200, 201, 204]:
            e = PostcardCreatorException('error in request {} {}. status_code: {}'
                                         .format(method, url, response.status_code))
            e.server_response = response.text
            raise e
        return response

    def get_user_info(self):
        logger.debug('fetching user information')
        endpoint = '/users/current'
        return self._do_op('get', endpoint).json()

    def get_billing_saldo(self):
        logger.debug('fetching billing saldo')

        user = self.get_user_info()
        endpoint = '/users/{}/billingOnlineAccountSaldo'.format(user["userId"])
        return self._do_op('get', endpoint).json()

    def get_quota(self):
        logger.debug('fetching quota')

        user = self.get_user_info()
        endpoint = '/users/{}/quota'.format(user["userId"])
        return self._do_op('get', endpoint).json()

    def has_free_postcard(self):
        return self.get_quota()['available']

    @_send_free_card_defaults
    def send_free_card(self, postcard, mock_send=False, **kwargs):
        if not self.has_free_postcard():
            raise PostcardCreatorException('Limit of free postcards exceeded. Try again tomorrow at '
                                           + self.get_quota()['next'])
        if not postcard:
            raise PostcardCreatorException('Postcard must be set')

        postcard.validate()
        user = self.get_user_info()
        user_id = user['userId']
        card_id = self._create_card(user)

        picture_stream = self._rotate_and_scale_image(postcard.picture_stream, **kwargs)
        asset_response = self._upload_asset(user, card_id=card_id, picture_stream=picture_stream)
        self._set_card_recipient(user_id=user_id, card_id=card_id, postcard=postcard)
        self._set_svg_page(1, user_id, card_id, postcard.get_frontpage(asset_id=asset_response['asset_id']))
        self._set_svg_page(2, user_id, card_id, postcard.get_backpage())

        if mock_send:
            response = False
            logger.debug('postcard was not sent because flag mock_send=True')
        else:
            response = self._do_order(user_id, card_id)
            logger.debug('postcard sent for printout')

        return response

    def _create_card(self, user):
        endpoint = '/users/{}/mailings'.format(user["userId"])

        mailing_payload = {
            'name': 'Mobile App Mailing {}'.format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
            'addressFormat': 'PERSON_FIRST',
            'paid': False
        }

        mailing_response = self._do_op('post', endpoint, json=mailing_payload)
        return mailing_response.headers['Location'].partition('mailings/')[2]

    def _upload_asset(self, user, card_id, picture_stream):
        logger.debug('uploading postcard asset')
        endpoint = '/users/{}/mailings/{}/assets'.format(user["userId"], card_id)

        files = {
            'title': (None, 'Title of image'),
            'asset': ('asset.png', picture_stream, 'image/jpeg')
        }
        headers = self._get_headers()
        headers['Origin'] = 'file://'
        response = self._do_op('post', endpoint, files=files, headers=headers)
        asset_id = response.headers['Location'].partition('user/')[2]

        return {
            'asset_id': asset_id,
            'response': response
        }

    def _set_card_recipient(self, user_id, card_id, postcard):
        logger.debug('set recipient for postcard')
        endpoint = '/users/{}/mailings/{}/recipients'.format(user_id, card_id)
        return self._do_op('put', endpoint, json=postcard.recipient.to_json())

    def _set_svg_page(self, page_number, user_id, card_id, svg_content):
        logger.debug('set svg template ' + str(page_number) + ' for postcard')
        endpoint = '/users/{}/mailings/{}/pages/{}'.format(user_id, card_id, page_number)

        headers = self._get_headers()
        headers['Origin'] = 'file://'
        headers['Content-Type'] = 'image/svg+xml'
        return self._do_op('put', endpoint, data=svg_content, headers=headers)

    def _do_order(self, user_id, card_id):
        logger.debug('submit postcard to be printed and delivered')
        endpoint = '/users/{}/mailings/{}/order'.format(user_id, card_id)
        return self._do_op('post', endpoint, json={})

    def _rotate_and_scale_image(self, file, image_target_width=154, image_target_height=111,
                                image_quality_factor=20, image_rotate=True, image_export=False):

        with Image.open(file) as image:
            if image_rotate and image.width < image.height:
                image = image.rotate(90, expand=True)
                logger.debug('rotating image by 90 degrees')

            if image.width < image_quality_factor * image_target_width \
                    or image.height < image_quality_factor * image_target_height:
                factor_width = math.floor(image.width / image_target_width)
                factor_height = math.floor(image.height / image_target_height)
                factor = min([factor_height, factor_width])

                logger.debug('image is smaller than default for resize/fill. '
                             'using scale factor {} instead of {}'.format(factor, image_quality_factor))
                image_quality_factor = factor

            width = image_target_width * image_quality_factor
            height = image_target_height * image_quality_factor
            logger.debug('resizing image from {}x{} to {}x{}'
                         .format(image.width, image.height, width, height))

            cover = resizeimage.resize_cover(image, [width, height], validate=True)
            with BytesIO() as f:
                cover.save(f, 'PNG')
                scaled = f.getvalue()

            if image_export:
                name = strftime("postcard_creator_export_%Y-%m-%d_%H-%M-%S.jpg", gmtime())
                path = os.path.join(os.getcwd(), name)
                logger.info('exporting image to {} (image_export=True)'.format(path))
                cover.save(path)

        return scaled


# expose Token class in this module for backwards compatibility
from postcard_creator.token import Token as T
Token = T

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(name)s (%(levelname)s): %(message)s')
    logging.getLogger('postcard_creator').setLevel(logging.DEBUG)
