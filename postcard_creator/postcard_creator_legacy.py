import datetime

import pkg_resources
import requests

from postcard_creator.postcard_creator import PostcardCreatorException, _dump_request, \
    _encode_text, _send_free_card_defaults, logger, PostcardCreatorBase
from postcard_creator.postcard_img_util import rotate_and_scale_image


def _format_recipient(recipient):
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
            [recipient.salutation,
             recipient.prename,
             recipient.lastname,
             recipient.company,
             recipient.company_addition,
             recipient.street,
             recipient.zip_code,
             recipient.place]]}


# XXX: 21-07-07, Legacy endpoints are out of life
@DeprecationWarning
class PostcardCreatorLegacy(PostcardCreatorBase):
    def __init__(self, token=None):
        if token.token is None:
            raise PostcardCreatorException('No Token given')
        self.token = token
        self.host = 'https://postcardcreator.post.ch/rest/2.2'
        self._session = self._create_session()

        self.frontpage_layout = pkg_resources.resource_string(__name__, 'page_1.svg').decode('utf-8')
        self.backpage_layout = pkg_resources.resource_string(__name__, 'page_2.svg').decode('utf-8')

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

        picture_stream = rotate_and_scale_image(postcard.picture_stream, **kwargs)
        asset_response = self._upload_asset(user, card_id=card_id, picture_stream=picture_stream)
        self._set_card_recipient(user_id=user_id, card_id=card_id, postcard=postcard)
        self._set_svg_page(1, user_id, card_id, self._get_frontpage(asset_id=asset_response['asset_id']))
        self._set_svg_page(2, user_id, card_id,
                           self._get_backpage(postcard.sender, postcard.recipient, postcard.message))

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
        return self._do_op('put', endpoint, json=_format_recipient(postcard.recipient))

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

    def _get_frontpage(self, asset_id):
        return self.frontpage_layout.replace('{asset_id}', str(asset_id))

    def _get_backpage(self, sender, recipient, message):
        svg = self.backpage_layout
        return svg \
            .replace('{first_name}', _encode_text(recipient.prename)) \
            .replace('{last_name}', _encode_text(recipient.lastname)) \
            .replace('{company}', _encode_text(recipient.company)) \
            .replace('{company_addition}', _encode_text(recipient.company_addition)) \
            .replace('{street}', _encode_text(recipient.street)) \
            .replace('{zip_code}', str(recipient.zip_code)) \
            .replace('{place}', _encode_text(recipient.place)) \
            .replace('{sender_company}', _encode_text(sender.company)) \
            .replace('{sender_name}', _encode_text(sender.prename) + ' ' + _encode_text(sender.lastname)) \
            .replace('{sender_address}', _encode_text(sender.street)) \
            .replace('{sender_zip_code}', str(sender.zip_code)) \
            .replace('{sender_place}', _encode_text(sender.place)) \
            .replace('{sender_country}', _encode_text(sender.country)) \
            .replace('{message}',
                     _encode_text(message))
