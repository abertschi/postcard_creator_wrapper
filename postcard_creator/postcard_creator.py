import logging
import requests
import json
from bs4 import BeautifulSoup
from requests_toolbelt.utils import dump
import datetime
import codecs
import tempfile
import pkg_resources
from pathlib import Path
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('postcard-creator')


class Debug(object):
    debug = False
    trace = False

    @staticmethod
    def log(msg):
        if Debug.debug:
            logger.info(msg)

    @staticmethod
    def trace_request(response):
        if Debug.trace:
            data = dump.dump_all(response)
            try:
                logger.info(data.decode())
            except Exception:
                data = str(data).replace('\\r\\n', '\r\n')
                logger.info("Failed to print request/response decoded. Printing it as byte string instead")
                logger.info(data)


class Token(object):
    base = 'https://account.post.ch'
    token_url = 'https://postcardcreator.post.ch/saml/SSO/alias/defaultAlias'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/52.0.2743.98 Mobile Safari/537.36',
        'Origin': 'https://account.post.ch'
    }
    # cache_filename = 'pcc_cache.json'

    def __init__(self):
        self.token = None
        self.token_type = None
        self.token_expires_in = None
        self.token_fetched_at = None
        self.cache_token = False

    def has_valid_credentials(self, username, password):
        try:
            self.fetch_token(username, password)
            return True
        except Exception:
            return False

    # def store_token_to_cache(self, key, token):
    #
    # def check_token_in_cache(self, username, password):
    #     tmp_dir = tempfile.gettempdir()
    #     tmp_path = os.path.join(tmp_dir, self.cache_filename)
    #     tmp_file = Path(tmp_path)
    #
    #     if tmp_file.exists():
    #         cache_content = open(tmp_file, "r").read()
    #         cache = []
    #         try:
    #             cache = json.load(cache_content)
    #         except Exception:
    #             return None
    #


    def fetch_token(self, username, password):
        if username is None or password is None:
            raise Exception('No username/ password given')

        # if self.cache_token:
        #     self.check_token_in_cache(username, password)

        session = requests.Session()
        payload = {
            'RelayState': 'https://postcardcreator.post.ch?inMobileApp=true&inIframe=false&lang=en',
            'SAMLResponse': self._get_saml_response(session, username, password)
        }

        response = session.post(url=self.token_url, headers=self.headers, data=payload)
        Debug.log(f' post {self.token_url}')
        Debug.trace_request(response)

        try:
            access_token = json.loads(response.text)

            self.token = access_token['access_token']
            self.token_type = access_token['token_type']
            self.token_expires_in = access_token['expires_in']
            self.token_fetched_at = datetime.datetime.now()

            if response.status_code is not 200 or self.token is None:
                raise Exception()

        except Exception:
            raise Exception(
                'Could not get access_token. Something broke. set Debug.debug/trace=True to debug why\n' + response.text)

        Debug.log(' username/password authentication successful')

    def _get_saml_response(self, session, username, password):
        url = f'{self.base}/SAML/IdentityProvider/'
        query = '?login&app=pcc&service=pcc&targetURL=https%3A%2F%2Fpostcardcreator.post.ch&abortURL=https%3A%2F%2Fpostcardcreator.post.ch&inMobileApp=true'
        data = {
            'isiwebuserid': username,
            'isiwebpasswd': password,
            'confirmLogin': ''
        }
        response1 = session.get(url=url + query, headers=self.headers)
        Debug.trace_request(response1)
        Debug.log(f' get {url}')

        response2 = session.post(url=url + query, headers=self.headers, data=data)
        Debug.trace_request(response2)
        Debug.log(f' post {url}')

        response3 = session.post(url=url + query, headers=self.headers)
        Debug.trace_request(response3)
        Debug.log(f' post {url}')

        if any(e.status_code is not 200 for e in [response1, response2, response3]):
            raise Exception('Wrong user credentials')

        soup = BeautifulSoup(response3.text, 'html.parser')
        saml_response = soup.find('input', {'name': 'SAMLResponse'})

        if saml_response is None or saml_response.get('value') is None:
            raise Exception('Username/password authentication failed. '
                            'Are your credentials valid?. set Debug.debug/trace=True for more information')

        return saml_response.get('value')

    def to_json(self):
        return {
            'fetched_at': self.token_fetched_at,
            'token': self.token,
            'expires_in': self.token_expires_in,
            'type': self.token_type,
        }


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
            raise Exception('Not all required attributes in recipient set')
        if self.recipient is None or not self.recipient.is_valid():
            raise Exception('Not all required attributes in sender set')

    def get_frontpage(self, user_id):
        return self.frontpage_layout.replace('{user_id}', str(user_id))

    def get_backpage(self):
        svg = self.backpage_layout

        return svg \
            .replace('{first_name}', self.recipient.prename) \
            .replace('{last_name}', self.recipient.lastname) \
            .replace('{company}', self.recipient.company) \
            .replace('{company_addition}', self.recipient.company_addition) \
            .replace('{street}', self.recipient.street) \
            .replace('{zip_code}', str(self.recipient.zip_code)) \
            .replace('{place}', self.recipient.place) \
            .replace('{sender_company}', self.sender.company) \
            .replace('{sender_name}', self.sender.prename + ' ' + self.sender.lastname) \
            .replace('{sender_address}', self.sender.street) \
            .replace('{sender_zip_code}', str(self.sender.zip_code)) \
            .replace('{sender_place}', self.sender.place) \
            .replace('{sender_country}', self.sender.country) \
            .replace('{message}',
                     self.message)  # TODO This is put into html block. Check if newlines need to be encoded as html tags


class PostcardCreator(object):
    def __init__(self, token=None):
        if token.token is None:
            raise Exception('No Token given')

        self.token = token
        self.host = 'https://postcardcreator.post.ch/rest/2.1'
        self._session = requests.Session()

    def _get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/52.0.2743.98 Mobile Safari/537.36',
            'Authorization': f'Bearer {self.token.token}'
        }

    def _do_op(self, method, endpoint, **kwargs):
        if not endpoint.endswith('/'):
            endpoint += '/'

        url = self.host + endpoint
        if 'headers' not in kwargs or kwargs['headers'] is None:
            kwargs['headers'] = self._get_headers()

        Debug.log(f' {method}: {url}')
        response = self._session.request(method, url, **kwargs)
        Debug.trace_request(response)

        if response.status_code not in [200, 201, 204]:
            raise Exception(
                f'Error in request {method} {url}. status_code: {response.status_code}, response:\n{response.text}')

        return response

    def get_user_info(self):
        endpoint = '/users/current'
        return self._do_op('get', endpoint).json()

    def get_billing_saldo(self):
        user = self.get_user_info()
        endpoint = f'/users/{user["userId"]}/billingOnlineAccountSaldo'
        return self._do_op('get', endpoint).json()

    def get_quota(self):
        user = self.get_user_info()
        endpoint = f'/users/{user["userId"]}/quota'
        return self._do_op('get', endpoint).json()

    def has_free_postcard(self):
        return self.get_quota()['available']

    def send_free_card(self, postcard, mock_send=False):
        if not self.has_free_postcard():
            raise Exception('Limit of free postcards exceeded. Try again tomorrow at ' + self.get_quota()['next'])
        if postcard is None:
            raise Exception('Postcard must be set')

        postcard.validate()
        user = self.get_user_info()
        user_id = user['userId']
        card_id = self._create_card(user)

        self._upload_asset(user, postcard=postcard)
        self._set_card_recipient(user_id=user_id, card_id=card_id, postcard=postcard)
        self._set_svg_page(1, user_id, card_id, postcard.get_frontpage(user_id))
        self._set_svg_page(2, user_id, card_id, postcard.get_backpage())

        if not mock_send:
            response = self._do_order(user_id, card_id)
            Debug.log('Postcard sent!')
        else:
            response = 'postcard was not sent'
            logger.info('Postcard was not sent. mock_send=True')

        return response

    def _create_card(self, user):
        endpoint = f'/users/{user["userId"]}/mailings'

        mailing_payload = {
            'name': f'Mobile App Mailing {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}',  # 2017-05-28 17:27
            'addressFormat': 'PERSON_FIRST',
            'paid': False
        }

        mailing_response = self._do_op('post', endpoint, json=mailing_payload)
        return mailing_response.headers['Location'].partition('mailings/')[2]

    def _upload_asset(self, user, postcard):
        endpoint = f'/users/{user["userId"]}/assets'

        files = {
            'title': (None, 'Title of image'),
            'asset': postcard.picture_stream
        }

        # 'title': (None, 'Title of image'),
        # 'asset': ('asset.png', bytes, 'image/jpeg')

        headers = self._get_headers()
        headers['Origin'] = 'file://'
        return self._do_op('post', endpoint, files=files, headers=headers)

    def _set_card_recipient(self, user_id, card_id, postcard):
        endpoint = f'/users/{user_id}/mailings/{card_id}/recipients'
        return self._do_op('put', endpoint, json=postcard.recipient.to_json())

    def _set_svg_page(self, page_number, user_id, card_id, svg_content):
        endpoint = f'/users/{user_id}/mailings/{card_id}/pages/{page_number}'

        headers = self._get_headers()
        headers['Origin'] = 'file://'
        headers['Content-Type'] = 'image/svg+xml'
        return self._do_op('put', endpoint, data=svg_content, headers=headers)

    def _do_order(self, user_id, card_id):
        endpoint = f'/users/{user_id}/mailings/{card_id}/order'
        return self._do_op('post', endpoint, json={})


if __name__ == '__main__':
    None
