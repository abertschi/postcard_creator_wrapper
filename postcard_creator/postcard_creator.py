import datetime
import logging
import math
import os
from io import BytesIO
from time import gmtime, strftime

import pkg_resources

from PIL import Image
from requests_toolbelt.utils import dump
from resizeimage import resizeimage

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

def _rotate_and_scale_image(file, image_target_width=154, image_target_height=111,
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

class PostcardCreator(object):

    def __init__(self, token=None):
        self.token = token
        if token.token is None:
            raise PostcardCreatorException('No Token given')
        if token.token_implementation == 'legacy':
            from postcard_creator.postcard_creator_legacy import PostcardCreatorLegacy
            self.impl = PostcardCreatorLegacy(token)
        else:
            self.impl = None

    def has_free_postcard(self):
        return self.impl.has_free_postcard()

    @_send_free_card_defaults
    def send_free_card(self, postcard, mock_send=False, **kwargs):
        return self.impl.send_free_card(postcard, mock_send, **kwargs)

    # XXX: In order to be downward compatible we
    # expose this class as a proxy for different endpoint implementations
    def __getattr__(self, method_name):
        def method(*args, **kwargs):
            logger.debug("Forwarding method to implementation {}: '{}'".
                         format(self.token.implementation_type, method_name))
            return getattr(self.impl, method_name)(*args, **kwargs)
        return method


class PostcardCreatorImpl(object):
    pass


# expose Token class in this module for backwards compatibility
from postcard_creator.token import Token as T

Token = T

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(name)s (%(levelname)s): %(message)s')
    logging.getLogger('postcard_creator').setLevel(logging.DEBUG)
