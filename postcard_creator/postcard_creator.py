import logging
import math
import os
from io import BytesIO
from pathlib import Path
from time import gmtime, strftime

from PIL import Image
from requests_toolbelt.utils import dump
from resizeimage import resizeimage

LOGGING_TRACE_LVL = 5
logger = logging.getLogger('postcard_creator')
logging.addLevelName(LOGGING_TRACE_LVL, 'TRACE')
setattr(logger, 'trace', lambda *args: logger.log(LOGGING_TRACE_LVL, *args))

def _get_trace_postcard_sent_dir():
    path = os.path.join(os.getcwd(), '.postcard_creator_wrapper_sent')
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


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
        kwargs['image_target_width'] = kwargs.get('image_target_width') or 154  # legacy only
        kwargs['image_target_height'] = kwargs.get('image_target_height') or 111  # legacy only
        kwargs['image_quality_factor'] = kwargs.get('image_quality_factor') or 20  # legacy only
        kwargs['image_rotate'] = kwargs.get('image_rotate') or True
        kwargs['image_export'] = kwargs.get('image_export') or False
        return func(*args, **kwargs)

    return wrapped

class PostcardCreator(object):
    def __init__(self, token=None):
        self.token = token

        if token.token is None:
            raise PostcardCreatorException('No Token given')
        # XXX: we no longer support 'legacy' endpoints as they are out of service
        # if token.token_implementation == 'legacy':
        #     from postcard_creator.postcard_creator_legacy import PostcardCreatorLegacy
        #     self.impl = PostcardCreatorLegacy(token)
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
