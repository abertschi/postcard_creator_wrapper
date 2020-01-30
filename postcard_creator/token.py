from bs4 import BeautifulSoup
from postcard_creator.postcard_creator import PostcardCreatorException
from requests_toolbelt.utils import dump

import datetime
import re
import urllib
import requests
import logging
import json


LOGGING_TRACE_LVL = 5
logger = logging.getLogger('postcard_creator')
logging.addLevelName(LOGGING_TRACE_LVL, 'TRACE')
setattr(logger, 'trace', lambda *args: logger.log(LOGGING_TRACE_LVL, *args))

swissid_headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; wv) ' +
                  'AppleWebKit/537.36 (KHTML, like Gecko) ' +
                  'Version/4.0 Chrome/52.0.2743.98 Mobile Safari/537.36',

    # the authenticate endpoint (step 3 and later) needs the following X headers to work
    'X-NoSession': 'true',
    'X-Password': 'anonymous',
    'X-Requested-With': 'XMLHttpRequest',
    'X-Username': 'anonymous'
}


def _log_response(h):
    for h in h.history:
        logger.debug(h.request.method + ': ' + str(h) + ' ' + h.url)
    logger.debug(h.request.method + ': ' + str(h) + ' ' + h.url)


def _dump_request(response):
    data = dump.dump_all(response)
    try:
        logger.trace(data.decode())
    except Exception:
        data = str(data).replace('\\r\\n', '\r\n')
        logger.trace(data)


def _log_and_dump(r):
    _log_response(r)
    _dump_request(r)


class Token(object):
    def __init__(self, _protocol='https://'):
        self.protocol = _protocol
        self.base = '{}account.post.ch'.format(self.protocol)
        self.swissid = '{}login.swissid.ch'.format(self.protocol)
        self.token_url = '{}postcardcreator.post.ch/saml/SSO/alias/defaultAlias'.format(self.protocol)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; wv) ' +
                          'AppleWebKit/537.36 (KHTML, like Gecko) ' +
                          'Version/4.0 Chrome/52.0.2743.98 Mobile Safari/537.36',
            'Origin': '{}account.post.ch'.format(self.protocol)
        }

        self.token = None
        self.token_type = None
        self.token_expires_in = None
        self.token_fetched_at = None
        self.cache_token = False

    def has_valid_credentials(self, username, password, method='mixed'):
        try:
            self.fetch_token(username, password, method=method)
            return True
        except PostcardCreatorException:
            return False

    def fetch_token(self, username, password, method='mixed'):
        logger.debug('fetching postcard account token')

        if username is None or password is None:
            raise PostcardCreatorException('No username/ password given')

        methods = ['mixed', 'legacy', 'swissid']
        if method not in methods:
            raise PostcardCreatorException('unknown method. choose from: ' + methods)

        session = None
        saml_response = None
        success = False
        if method != 'swissid':
            logging.info("using legacy username password authentication")
            try:
                session = self._create_session()
                saml_response = self._get_legacy_saml_response(session, username, password)
                success = True
            except PostcardCreatorException as e:
                logging.info("legacy username password authentication failed")
                logging.error(e)

        if method != 'legacy' and not success:
            logging.info("using swissid username password authentication")
            try:
                session = self._create_session()
                saml_response = self._get_swissid_saml_response(session, username, password)
            except PostcardCreatorException as e:
                logging.info("swissid username password authentication failed")
                logging.error(e)

        payload = {
            'RelayState': '{}postcardcreator.post.ch?inMobileApp=true&inIframe=false&lang=en'.format(self.protocol),
            'SAMLResponse': saml_response
        }

        response = session.post(url=self.token_url, headers=self.headers, data=payload)
        logger.debug(' post {}'.format(self.token_url))
        _dump_request(response)

        try:
            if response.status_code != 200:
                raise PostcardCreatorException()

            access_token = json.loads(response.text)
            self.token = access_token['access_token']
            self.token_type = access_token['token_type']
            self.token_expires_in = access_token['expires_in']
            self.token_fetched_at = datetime.datetime.now()

        except PostcardCreatorException:
            e = PostcardCreatorException(
                'Could not get access_token. Something broke. '
                'set increase debug verbosity to debug why')
            e.server_response = response.text
            raise e

        logger.debug('username/password authentication was successful')

    def _create_session(self):
        return requests.Session()

    def _get_legacy_saml_response(self, session, username, password):
        url = '{}/SAML/IdentityProvider/'.format(self.base)
        query = '?login&app=pcc&service=pcc&targetURL=https%3A%2F%2Fpostcardcreator.post.ch' + \
                '&abortURL=https%3A%2F%2Fpostcardcreator.post.ch&inMobileApp=true'
        data = {
            'isiwebuserid': username,
            'isiwebpasswd': password,
            'confirmLogin': ''
        }
        response1 = session.get(url=url + query, headers=self.headers)
        _dump_request(response1)
        logger.debug(' get {}'.format(url))

        response2 = session.post(url=url + query, headers=self.headers, data=data)
        _dump_request(response2)
        logger.debug(' post {}'.format(url))

        response3 = session.post(url=url + query, headers=self.headers)
        _dump_request(response3)
        logger.debug(' post {}'.format(url))

        if any(e.status_code != 200 for e in [response1, response2, response3]):
            raise PostcardCreatorException('Wrong user credentials')

        soup = BeautifulSoup(response3.text, 'html.parser')
        saml_response = soup.find('input', {'name': 'SAMLResponse'})

        if saml_response is None or saml_response.get('value') is None:
            raise PostcardCreatorException('Username/password authentication failed. '
                                           'Are your credentials valid?.')

        return saml_response.get('value')

    def _get_swissid_saml_response(self, session, username, password):
        logger.debug("--- 1. request swissid portal website")
        step1_url = 'https://account.post.ch/SAML/IdentityProvider/?login&'
        step1_query = {
            'app': 'pcc',
            'service': 'pcc',
            'targetURL': 'https://postcardcreator.post.ch',
            'abortURL': 'https://postcardcreator.post.ch'
        }
        step1_payload = {
            'externalIDP': 'externalIDP'
        }
        step1_r = session.post(step1_url + urllib.parse.urlencode(step1_query),
                               data=step1_payload, allow_redirects=True,
                               headers=swissid_headers)
        _log_and_dump(step1_r)
        if len(step1_r.history) == 0:
            raise PostcardCreatorException('step 1 in swissid authentication requires redirections. not avalable' +
                                           'did something break?')
        step1_goto_url = step1_r.history[len(step1_r.history) - 1]

        logger.debug("--- 2. follow redirects and get goto_param")
        step2_url = 'https://login.swissid.ch/idp/json/realms/root/realms/sesam/serverinfo/*'
        step2_r = session.get(step2_url, allow_redirects=True)
        _log_and_dump(step2_r)

        goto_param = re.search(r'&goto=(.*?)$', step1_goto_url.url).group(1)
        logger.trace("goto parm=" + goto_param)
        if goto_param is None or goto_param == '':
            raise PostcardCreatorException('step 2 in swissid authentication failed: no goto found')

        logger.debug("--- 3. get web form for username/password")
        step3_url = 'https://login.swissid.ch/idp/json/realms/root/realms/sesam/authenticate?' + \
                    'locale=en&authIndexType=service&authIndexValue=Sesam-Push-Auth&goto=' + goto_param
        step3_r = session.post(step3_url, data='', headers=swissid_headers)
        _log_and_dump(step3_r)

        logger.debug("--- 4. submit username")
        step3_json = step3_r.json()
        logger.trace(step3_json)

        step3_found_user = False
        try:
            for c in step3_json['callbacks']:
                if c.get('type') == 'NameCallback':
                    c['input'][0]['value'] = username
                    step3_found_user = True
                    break
        except Exception:
            pass
        if not step3_found_user:
            raise PostcardCreatorException('step4 in swissid authentication failed. no username response found.')

        step4_r = session.post(step3_url, json=step3_json, headers=swissid_headers)
        _log_and_dump(step4_r)

        logger.debug("--- 5. submit password")
        step5_json = step4_r.json()
        step5_found_password = False
        try:
            for c in step5_json['callbacks']:
                if c.get('type') == 'PasswordCallback':
                    c['input'][0]['value'] = password
                    step5_found_password = True
                    break
        except Exception:
            pass
        if not step5_found_password:
            raise PostcardCreatorException('step5 in swissid authentication failed. are your credentials correct?')
            pass

        step5_r = session.post(step3_url, json=step5_json, headers=swissid_headers)
        _log_and_dump(step5_r)

        logger.debug("--- 6. follow a redirects to get SAML endpoint")
        step6_r = session.get(urllib.parse.unquote(goto_param), allow_redirects=True, headers=swissid_headers)
        _log_and_dump(step6_r)

        logger.debug("--- step 7. get SAML response")
        step7_r = session.post(step6_r.url, headers=swissid_headers)
        _log_and_dump(step7_r)

        step7_soup = BeautifulSoup(step7_r.text, 'html.parser')
        saml_response = step7_soup.find('input', {'name': 'SAMLResponse'})

        if saml_response is None or saml_response.get('value') is None:
            raise PostcardCreatorException('Username/password authentication failed. '
                                           'Are your credentials valid?.')

        return saml_response.get('value')

    def to_json(self):
        return {
            'fetched_at': self.token_fetched_at,
            'token': self.token,
            'expires_in': self.token_expires_in,
            'type': self.token_type,
        }