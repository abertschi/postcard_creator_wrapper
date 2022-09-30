import base64
import datetime
import hashlib
import logging
import re
import secrets
import urllib
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests_toolbelt.utils import dump
from urllib3 import Retry

from postcard_creator.postcard_creator import PostcardCreatorException

LOGGING_TRACE_LVL = 5
logger = logging.getLogger('postcard_creator')
logging.addLevelName(LOGGING_TRACE_LVL, 'TRACE')
setattr(logger, 'trace', lambda *args: logger.log(LOGGING_TRACE_LVL, *args))


def base64_encode(string):
    encoded = base64.urlsafe_b64encode(string).decode('ascii')
    return encoded.rstrip("=")


def base64_decode(string):
    padding = 4 - (len(string) % 4)
    string = string + ("=" * padding)
    return base64.urlsafe_b64decode(string)


def _log_response(h):
    for h in h.history:
        logger.debug(h.request.method + ': ' + str(h) + ' ' + h.url)
    logger.debug(h.request.method + ': ' + str(h) + ' ' + h.url)


def _print_request(response):
    logger.debug(' {} {} [{}]'.format(response.request.method, response.request.url, response.status_code))


def _dump_request(response):
    _print_request(response)
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
        self.user_agent = 'Mozilla/5.0 (Linux; Android 6.0.1; wv) ' + \
                          'AppleWebKit/537.36 (KHTML, like Gecko) ' + \
                          'Version/4.0 Chrome/52.0.2743.98 Mobile Safari/537.36'
        self.legacy_headers = {
            'User-Agent': self.user_agent
        }
        self.swissid_headers = {
            'User-Agent': self.user_agent
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

        success = False
        access_token = None
        implementation_type = ''
        if method != 'swissid':
            logger.info("using legacy username password authentication")
            session = self._create_session()
            try:
                access_token = self._get_access_token_legacy(session, username, password)
                logger.debug('legacy username/password authentication was successful')
                success = True
                implementation_type = 'legacy'
            except Exception as e:
                logger.info("legacy username password authentication failed")
                logger.info(e)
                if method == 'mixed':
                    logger.info("Trying swissid now because method=legacy")
                else:
                    logger.info("giving up")
                    raise e
                pass
        if method != 'legacy' and not success:
            logger.info("using swissid username password authentication")
            try:
                session = self._create_session()
                access_token = self._get_access_token_swissid(session, username, password)
                logger.debug('swissid username/password authentication was successful')
                implementation_type = 'swissid'
            except Exception as e:
                logger.info("swissid username password authentication failed")
                logger.info(e)
                raise e

        try:
            logger.trace(access_token)
            self.token = access_token['access_token']
            self.token_type = access_token['token_type']
            self.token_expires_in = access_token['expires_in']
            self.token_fetched_at = datetime.datetime.now()
            self.token_implementation = implementation_type
            logger.info("access_token successfully fetched")

        except Exception as e:
            logger.info("access_token does not contain required values. someting broke")
            raise e

    def _create_session(self, retries=5, backoff_factor=0.5, status_forcelist=(500, 502, 504)):
        # XXX: Backend will terminate connection if we request too frequently
        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _get_code_verifier(self):
        return base64_encode(secrets.token_bytes(64))

    def _get_code(self, code_verifier):
        m = hashlib.sha256()
        m.update(code_verifier.encode('utf-8'))
        return base64_encode(m.digest())

    def _get_access_token_legacy(self, session, username, password):
        code_verifier = self._get_code_verifier()
        code_resp_uri = self._get_code(code_verifier)
        redirect_uri = 'ch.post.pcc://auth/1016c75e-aa9c-493e-84b8-4eb3ba6177ef'
        client_id = 'ae9b9894f8728ca78800942cda638155'
        client_secret = '89ff451ede545c3f408d792e8caaddf0'
        init_data = {
            'client_id': client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': 'PCCWEB offline_access',
            'response_mode': 'query',
            'state': 'abcd',
            'code_challenge': code_resp_uri,
            'code_challenge_method': 'S256',
            'lang': 'en'
        }
        url = 'https://pccweb.api.post.ch/OAuth/authorization?'
        resp = session.get(url + urllib.parse.urlencode(init_data),
                           allow_redirects=True,
                           headers=self.legacy_headers)
        _log_and_dump(resp)

        url_payload = {
            'targetURL': 'https://pccweb.api.post.ch/SAML/ServiceProvider/?redirect_uri=' + redirect_uri,
            'profile': 'default',
            'app': 'pccwebapi',
            'inMobileApp': 'true',
            'layoutType': 'standard'
        }
        data_payload = {
            'isiwebuserid': username,
            'isiwebpasswd': password,
            'confirmLogin': '',
        }
        url = 'https://account.post.ch/idp/?login&'
        resp = session.post(url + urllib.parse.urlencode(url_payload),
                            allow_redirects=True,
                            headers=self.legacy_headers, data=data_payload)
        _log_and_dump(resp)

        resp = session.post(url + urllib.parse.urlencode(url_payload),
                            allow_redirects=True,
                            headers=self.legacy_headers)

        saml_soup = BeautifulSoup(resp.text, 'html.parser')
        saml_response = saml_soup.find('input', {'name': 'SAMLResponse'})

        if saml_response is None or saml_response.get('value') is None:
            raise PostcardCreatorException('Username/password authentication failed. Are your credentials valid?.')

        saml_response = saml_response['value']
        relay_state = saml_soup.find('input', {'name': 'RelayState'})['value'],

        url = "https://pccweb.api.post.ch/OAuth/"  # important: '/' at the end
        customer_headers = self.legacy_headers
        customer_headers['Origin'] = 'https://account.post.ch'
        customer_headers['X-Requested-With'] = 'ch.post.it.pcc'
        customer_headers['Upgrade-Insecure-Requests'] = str(1)
        saml_payload = {
            'RelayState': relay_state,
            'SAMLResponse': saml_response
        }
        resp = session.post(url,
                            headers=customer_headers,
                            data=saml_payload,
                            allow_redirects=False)  # do not follow redirects as we cannot redirect to android uri
        try:
            code_resp_uri = resp.headers['Location']
            init_data = parse_qs(urlparse(code_resp_uri).query)
            resp_code = init_data['code'][0]
        except Exception as e:
            print(e)
            raise PostcardCreatorException('response does not have code attribute: ' + url + '. Did endpoint break?')

        # get access token
        data = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'code': resp_code,
            'code_verifier': code_verifier,
            'redirect_uri': redirect_uri,
        }
        url = 'https://pccweb.api.post.ch/OAuth/token'
        resp = requests.post(url,
                             data=data,
                             headers=self.legacy_headers,
                             allow_redirects=False)
        _log_and_dump(resp)

        if 'access_token' not in resp.json() or resp.status_code != 200:
            raise PostcardCreatorException("not able to fetch access token: " + resp.text)

        return resp.json()

    def _get_access_token_swissid(self, session, username, password):
        code_verifier = self._get_code_verifier()
        code_resp_uri = self._get_code(code_verifier)
        redirect_uri = 'ch.post.pcc://auth/1016c75e-aa9c-493e-84b8-4eb3ba6177ef'
        client_id = 'ae9b9894f8728ca78800942cda638155'
        client_secret = '89ff451ede545c3f408d792e8caaddf0'

        init_data = {
            'client_id': client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': 'PCCWEB offline_access',
            'response_mode': 'query',
            'state': 'abcd',
            'code_challenge': code_resp_uri,
            'code_challenge_method': 'S256',
            'lang': 'en'
        }
        url = 'https://pccweb.api.post.ch/OAuth/authorization?'
        resp = session.get(url + urllib.parse.urlencode(init_data),
                           allow_redirects=True,
                           headers=self.swissid_headers)
        _log_and_dump(resp)

        saml_payload = {
            'externalIDP': 'externalIDP'
        }
        url = 'https://account.post.ch/idp/?login' \
              '&targetURL=https://pccweb.api.post.ch/SAML/ServiceProvider/' \
              '?redirect_uri=' + redirect_uri + \
              '&profile=default' \
              '&app=pccwebapi&inMobileApp=true&layoutType=standard'
        resp = session.post(url,
                            data=saml_payload,
                            allow_redirects=True,
                            headers=self.swissid_headers)
        _log_and_dump(resp)
        if len(resp.history) == 0:
            raise PostcardCreatorException('fail to fetch ' + url)

        step1_goto_url = resp.history[len(resp.history) - 1].headers['Location']
        goto_param = re.search(r'goto=(.*?)$', step1_goto_url).group(1)
        try:
            goto_param = goto_param.split('&')[0]
        except Exception as e:
            # only use goto_param without further params
            pass
        logger.trace("goto parm=" + goto_param)
        if goto_param is None or goto_param == '':
            raise PostcardCreatorException('swissid: cannot fetch goto param')

        url = "https://login.swissid.ch/api-login/authenticate/token/status?locale=en&goto=" + goto_param + \
              "&acr_values=loa-1&realm=%2Fsesam&service=qoa1"
        resp = session.get(url, allow_redirects=True)
        _log_and_dump(resp)

        url = "https://login.swissid.ch/api-login/welcome-pack?locale=en" + goto_param + \
              "&acr_values=loa-1&realm=%2Fsesam&service=qoa1"
        resp = session.get(url, allow_redirects=True)
        _log_and_dump(resp)

        # login with username and password
        url = 'https://login.swissid.ch/api-login/authenticate/init?locale=en&goto=' + goto_param + \
              "&acr_values=loa-1&realm=%2Fsesam&service=qoa1"
        resp = session.post(url, allow_redirects=True)
        _log_and_dump(resp)

        # submit username and password
        url_query_string = "locale=en&goto=" + goto_param + \
                           "&acr_values=loa-1&realm=%2Fsesam&service=qoa1"

        url = "https://login.swissid.ch/api-login/authenticate/basic?" + url_query_string
        headers = self.swissid_headers
        headers['authId'] = resp.json()['tokens']['authId']
        step_data = {
            'username': username,
            'password': password
        }
        resp = session.post(url, json=step_data, headers=headers, allow_redirects=True)
        _log_and_dump(resp)

        # anomaly detection
        resp = self._swiss_id_anomaly_detection(session, resp, url_query_string)

        try:
            url = resp.json()['nextAction']['successUrl']
        except Exception as e:
            logger.info("failed to login. username/password wrong?")
            raise PostcardCreatorException("failed to login, username/password wrong?")

        resp = session.get(url, headers=self.swissid_headers, allow_redirects=True)
        _log_and_dump(resp)

        step7_soup = BeautifulSoup(resp.text, 'html.parser')
        url = step7_soup.find('form', {'name': 'LoginForm'})['action']
        resp = session.post(url, headers=self.swissid_headers)
        _log_and_dump(resp)

        # find saml response
        step7_soup = BeautifulSoup(resp.text, 'html.parser')
        saml_response = step7_soup.find('input', {'name': 'SAMLResponse'})

        if saml_response is None or saml_response.get('value') is None:
            raise PostcardCreatorException('Username/password authentication failed. Are your credentials valid?.')

        # prepare access token
        url = "https://pccweb.api.post.ch/OAuth/"  # important: '/' at the end
        customer_headers = self.swissid_headers
        customer_headers['Origin'] = 'https://account.post.ch'
        customer_headers['X-Requested-With'] = 'ch.post.it.pcc'
        customer_headers['Upgrade-Insecure-Requests'] = str(1)
        saml_payload = {
            'RelayState': step7_soup.find('input', {'name': 'RelayState'})['value'],
            'SAMLResponse': saml_response.get('value')
        }
        resp = session.post(url, headers=customer_headers,
                            data=saml_payload,
                            allow_redirects=False)  # do not follow redirects as we cannot redirect to android uri
        try:
            code_resp_uri = resp.headers['Location']
            init_data = parse_qs(urlparse(code_resp_uri).query)
            resp_code = init_data['code'][0]
        except Exception as e:
            print(e)
            raise PostcardCreatorException('response does not have code attribute: ' + url + '. Did endpoint break?')

        # get access token
        data = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'code': resp_code,
            'code_verifier': code_verifier,
            'redirect_uri': redirect_uri,
        }
        url = 'https://pccweb.api.post.ch/OAuth/token'
        resp = requests.post(url,  # we do not use session here!
                             data=data,
                             headers=self.swissid_headers,
                             allow_redirects=False)
        _log_and_dump(resp)

        if 'access_token' not in resp.json() or resp.status_code != 200:
            raise PostcardCreatorException("not able to fetch access token: " + resp.text)

        return resp.json()

    def _swiss_id_anomaly_detection(self, session, prev_response, url_query_string):
        # XXX: Starting 2022-10, endpoints introduce anomaly detection, possibly to further restrict automated access
        # Currently, any valid device_print payload seems to work
        # useragent in request and payload can differ and still be valid
        url = 'https://login.swissid.ch/api-login/anomaly-detection/device-print?' + url_query_string
        device_print_ctx = prev_response.json()
        try:
            next_action = device_print_ctx['nextAction']['type']
            if next_action != 'SEND_DEVICE_PRINT':
                logger.warning('next action must be SEND_DEVICE_PRINT but got ' + next_action)
            auth_id_device_print = device_print_ctx['tokens']['authId']
            device_print = self._formulate_anomaly_detection()
            headers = self.swissid_headers
            headers['authId'] = auth_id_device_print
            resp = session.post(url, json=device_print, headers=headers)
            _log_and_dump(resp)
        except Exception as e:
            msg = "Anomaly detection step failed. \n" \
                  + f"previous response body: {device_print_ctx}\n" \
                  + f"pending request: {url} \n"
            logger.info(msg)
            logger.info(e)
            raise PostcardCreatorException(msg, e)
        return resp

    def _formulate_anomaly_detection(self):
        # Valid device_print generated in an x86 android 12 emulator,
        # XXX: if something breaks in the future, we may have to get more clever here
        device_print = {
            "appCodeName": "Mozilla",
            "appName": "Netscape",
            "appVersion": self.user_agent.replace('Mozilla/', ''),  # Mozilla/5.0
            "fonts": {
                "installedFonts": "cursive;monospace;serif;sans-serif;fantasy;default;Arial;Courier;" + \
                                  "Courier New;Georgia;Tahoma;Times;Times New Roman;Verdana"
            },
            "language": "de",
            "platform": "Linux x86_64",
            "plugins": {
                "installedPlugins": ""
            },
            "product": "Gecko",
            "productSub": "20030107",
            "screen": {
                "screenColourDepth": 24,
                "screenHeight": 732,
                "screenWidth": 412
            },
            "timezone": {
                "timezone": -120
            },
            "userAgent": self.user_agent,
            "vendor": "Google Inc."
        }

        return device_print

    def to_json(self):
        return {
            'fetched_at': self.token_fetched_at,
            'token': self.token,
            'expires_in': self.token_expires_in,
            'type': self.token_type,
            'implementation': self.token_implementation
        }
