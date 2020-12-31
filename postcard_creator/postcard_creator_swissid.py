import base64
import io
import os
import textwrap
from math import floor
from time import gmtime, strftime

import pkg_resources
import requests
from PIL import Image, ImageDraw, ImageFont

from postcard_creator.postcard_creator import PostcardCreatorBase, PostcardCreatorException, Recipient, Sender, \
    _dump_request, _encode_text, _get_trace_postcard_sent_dir, _rotate_and_scale_image, _send_free_card_defaults, logger


def _format_sender(sender: Sender):
    return {
        'city': _encode_text(sender.place),
        'company': _encode_text(sender.company),
        'firstname': _encode_text(sender.prename),
        'lastname': _encode_text(sender.lastname),
        'street': _encode_text(sender.street),
        'zip': sender.zip_code
    }


def _format_recipient(recipient: Recipient):
    return {
        'city': _encode_text(recipient.place),
        'company': _encode_text(recipient.company),
        'companyAddon': _encode_text(recipient.company_addition),
        'country': 'SWITZERLAND',
        'firstname': _encode_text(recipient.prename),
        'lastname': _encode_text(recipient.lastname),
        'street': _encode_text(recipient.street),
        'title': _encode_text(recipient.salutation),
        'zip': recipient.zip_code,
    }


class PostcardCreatorSwissId(PostcardCreatorBase):
    def __init__(self, token=None):
        if token.token is None:
            raise PostcardCreatorException('No Token given')
        self.token = token
        self._session = self._create_session()
        self.host = 'https://pccweb.api.post.ch/secure/api/mobile/v1'

    def _get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; wv) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Version/4.0 Chrome/52.0.2743.98 Mobile Safari/537.36',
            'Authorization': 'Bearer {}'.format(self.token.token)
        }

    def _create_session(self):
        return requests.Session()

    # XXX: we share some functionality with legacy wrapper here
    # however, it is little and not worth the lack of extensibility if generalized in super class
    def _do_op(self, method, endpoint, **kwargs):
        url = self.host + endpoint
        if 'headers' not in kwargs or kwargs['headers'] is None:
            kwargs['headers'] = self._get_headers()

        logger.debug('{}: {}'.format(method, url))
        response = self._session.request(method, url, **kwargs)
        _dump_request(response)

        if response.status_code not in [200, 201, 204]:
            e = PostcardCreatorException('error in request {} {}. status_code: {}, text: {}'
                                         .format(method, url, response.status_code, response.text or ''))
            e.server_response = response.text
            raise e
        return response

    def _validate_model_response(self, endpoint, payload):
        if payload.get('errors'):
            raise PostcardCreatorException(f'cannot fetch {endpoint}: {payload["errors"]}')

    def get_quota(self):
        logger.debug('fetching quota')
        endpoint = '/user/quota'

        payload = self._do_op('get', endpoint).json()
        self._validate_model_response(endpoint, payload)
        return payload['model']

    def has_free_postcard(self):
        return self.get_quota()['available']

    def get_user_info(self):
        logger.debug('fetching user information')
        endpoint = '/user/current'

        payload = self._do_op('get', endpoint).json()
        self._validate_model_response(endpoint, payload)
        return payload['model']

    def get_billing_saldo(self):
        logger.debug('fetching billing saldo')
        endpoint = '/billingOnline/accountSaldo'

        payload = self._do_op('get', endpoint).json()
        self._validate_model_response(endpoint, payload)
        return payload['model']

    @_send_free_card_defaults
    def send_free_card(self, postcard, mock_send=False, image_export=False, **kwargs):
        if not postcard:
            raise PostcardCreatorException('Postcard must be set')
        postcard.validate()

        # XXX: endpoint no longer supports user specified w/h
        kwargs['image_target_width'] = 1819
        kwargs['image_quality_factor'] = 1
        kwargs['image_target_height'] = 1311
        img_base64 = base64.b64encode(_rotate_and_scale_image(postcard.picture_stream,
                                                              img_format='jpeg',
                                                              image_export=image_export,
                                                              **kwargs)).decode('ascii')

        img_text_base64 = base64.b64encode(self.create_text_image(postcard.message,
                                                                  image_export=image_export)).decode('ascii')
        endpoint = '/card/upload'
        payload = {
            'lang': 'en',
            'paid': False,
            'recipient': _format_recipient(postcard.recipient),
            'sender': _format_sender(postcard.sender),
            'text': '',
            'textImage': img_text_base64,  # jpeg, JFIF standard 1.01, 720x744
            'image': img_base64,  # jpeg, JFIF standard 1.01, 1819x1311
            'stamp': None
        }

        if mock_send:
            copy = dict(payload)
            copy['textImage'] = 'omitted'
            copy['image'] = 'omitted'
            logger.info(f'mock_send=True, endpoint: {endpoint}, payload: {copy}')
            return False

        if not self.has_free_postcard():
            raise PostcardCreatorException('Limit of free postcards exceeded. Try again tomorrow at '
                                           + self.get_quota()['next'])

        payload = self._do_op('post', endpoint, json=payload).json()
        logger.debug(f'{endpoint} with response {payload}')

        self._validate_model_response(endpoint, payload)

        logger.info(f'postcard submitted, orderid {payload.get("orderId")}')
        return payload

    def create_text_image(self, text, image_export=False, **kwargs):
        """
        Create a jpg with given text and return in bytes format, overwrite for customizations
        """
        text_canvas_w = 720
        text_canvas_h = 744
        text_canvas_bg = 'white'
        text_canvas_fg = 'black'
        text_canvas_font_name = 'open_sans_emoji.ttf'

        def load_font(size):
            return ImageFont.truetype(pkg_resources.resource_stream(__name__, text_canvas_font_name), size)

        def find_optimal_size(msg, min_size=20, max_size=400, min_line_w=1, max_line_w=80, padding=0):
            """
            Find optimal font size and line width for a given text
            """

            def line_width(font_size, padding=70):
                l = min_line_w
                r = max_line_w
                font = load_font(font_size)
                while l < r:
                    n = floor((l + r) / 2)
                    t = ''.join([char * n for char in '1'])
                    font_w, font_h = font.getsize(t)
                    font_w = font_w + (2 * padding)
                    if font_w >= text_canvas_w:
                        r = n - 1
                        pass
                    else:
                        l = n + 1
                        pass
                return n

            size_l = min_size
            size_r = max_size
            last_line_w = 0
            last_size = 0

            while size_l <= size_r:
                size = floor((size_l + size_r) / 2.0)
                last_size = size
                line_w = line_width(size)
                last_line_w = line_w

                lines = textwrap.wrap(msg, width=line_w)
                font = load_font(size)
                total_w, line_h = font.getsize(msg)
                tot_height = len(lines) * line_h

                if tot_height + (2 * padding) < text_canvas_h:
                    start_y = (text_canvas_h - tot_height) / 2
                else:
                    start_y = 0

                if start_y == 0:
                    size_r = size - 1
                else:
                    size_l = size + 1

            return last_size, last_line_w

        def center_y(lines, font_h):
            tot_height = len(lines) * font_h
            if tot_height < text_canvas_h:
                return (text_canvas_h - tot_height) / 2
            else:
                return 0

        size, line_w = find_optimal_size(text, padding=50)
        logger.debug(f'using font with size: {size}, width: {line_w}')

        font = load_font(size)
        font_w, font_h = font.getsize(text)
        lines = textwrap.wrap(text, width=line_w)
        text_y_start = center_y(lines, font_h)

        canvas = Image.new('RGB', (text_canvas_w, text_canvas_h), text_canvas_bg)
        draw = ImageDraw.Draw(canvas)
        for line in lines:
            width, height = font.getsize(line)
            draw.text(((text_canvas_w - width) / 2, text_y_start), line,
                      font=font,
                      fill=text_canvas_fg,
                      embedded_color=True)
            text_y_start += (height)

        if image_export:
            name = strftime("postcard_creator_export_%Y-%m-%d_%H-%M-%S_text.jpg", gmtime())
            path = os.path.join(_get_trace_postcard_sent_dir(), name)
            logger.info('exporting image to {} (image_export=True)'.format(path))
            canvas.save(path)

        img_byte_arr = io.BytesIO()
        canvas.save(img_byte_arr, format='jpeg')
        return img_byte_arr.getvalue()
