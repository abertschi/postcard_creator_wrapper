import logging
import math
import os
from io import BytesIO
from time import gmtime, strftime

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
            from postcard_creator.postcard_creator_swissid import PostcardCreatorSwissId
            self.impl = PostcardCreatorSwissId(token)

    # XXX: In order to be downward compatible we
    # expose this class as a proxy for different endpoint implementations
    def __getattr__(self, method_name):
        def method(*args, **kwargs):
            logger.debug("Forwarding method to implementation {}: '{}'".
                         format(self.token.token_implementation, method_name))
            return getattr(self.impl, method_name)(*args, **kwargs)

        return method


class PostcardCreatorBase(object):
    def has_free_postcard(self):
        pass

    @_send_free_card_defaults
    def send_free_card(self, postcard, mock_send=False, **kwargs):
        pass

    def get_quota(self):
        """
        Format: {'quota': -1, 'retentionDays': 1, 'available': False, 'next': '2020-12-24T18:00:15+01:00'}
        """
        pass


# expose Token class in this module for backwards compatibility
from postcard_creator.token import Token as T

Token = T

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(name)s (%(levelname)s): %(message)s')
    logging.getLogger('postcard_creator').setLevel(logging.DEBUG)
