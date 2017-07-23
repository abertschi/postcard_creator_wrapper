from postcard_creator.postcard_creator import PostcardCreator, Token, Postcard, PostcardCreatorException
import requests
import requests_mock
import logging
import pkg_resources
import json
import pytest

logging.basicConfig(level=logging.INFO,
                    format='%(name)s (%(levelname)s): %(message)s')
logging.getLogger('postcard_creator').setLevel(10)

URL_TOKEN_SAML = 'mock://account.post.ch/SAML/IdentityProvider/'
URL_TOKEN_SSO = 'mock://postcardcreator.post.ch/saml/SSO/alias/defaultAlias'

adapter = None


def create_mocked_session(self):
    global adapter
    session = requests.Session()
    session.mount('mock', adapter)
    return session


def create_token():
    global adapter
    adapter = requests_mock.Adapter()
    Token._create_session = create_mocked_session
    return Token(_protocol='mock://')


def create_token_with_successful_login():
    token = create_token()
    saml_response = pkg_resources.resource_string(__name__, 'saml_response.html').decode('utf-8')
    access_token = {
        'access_token': 0,
        'token_type': 'token_type',
        'expires_in': 3600
    }

    adapter.register_uri('GET', URL_TOKEN_SAML, text='', reason='')
    adapter.register_uri('POST', URL_TOKEN_SAML, reason='', text=saml_response)
    adapter.register_uri('POST', URL_TOKEN_SSO, reason='', text=json.dumps(access_token))
    return token


def test_token_invalid_args():
    with pytest.raises(PostcardCreatorException):
        token = create_token()
        token.fetch_token(None, None)


def test_token_wrong_user_credentials():
    token = create_token()
    adapter.register_uri('GET', URL_TOKEN_SAML, text='', reason='', status_code=500)
    adapter.register_uri('POST', URL_TOKEN_SAML, reason='', text='')
    adapter.register_uri('POST', URL_TOKEN_SSO, reason='', text='')

    with pytest.raises(PostcardCreatorException):
        token.fetch_token('username', 'password')


def test_token_saml_invalid_response():
    token = create_token_with_successful_login()
    saml_response = pkg_resources.resource_string(__name__, 'saml_response_invalid.html').decode('utf-8')
    adapter.register_uri('POST', URL_TOKEN_SAML, reason='', text=saml_response)

    with pytest.raises(PostcardCreatorException):
        token.fetch_token('username', 'password')


def test_token_invalid_token_returned():
    token = create_token_with_successful_login()
    adapter.register_uri('POST', URL_TOKEN_SSO, reason='', text=json.dumps(''), status_code=500)

    with pytest.raises(PostcardCreatorException):
        token.fetch_token('username', 'password')


def test_token_fetch_token_successful():
    token = create_token_with_successful_login()
    token.fetch_token('username', 'password')

    assert token.token == 0
    assert token.token_type == 'token_type'
    assert token.token_expires_in == 3600


def test_token_has_valid_credential():
    token = create_token_with_successful_login()
    assert token.has_valid_credentials('username', 'password')
