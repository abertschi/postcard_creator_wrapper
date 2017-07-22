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


def test_token_invalid_args():
    with pytest.raises(PostcardCreatorException):
        token = create_token()
        token.fetch_token(None, None)


def test_token_wrong_user_credentials():
    with pytest.raises(PostcardCreatorException):
        token = create_token()
        token.fetch_token('username', 'password')

    pass


def test_token_saml_invalid_response():
    pass


def test_token_invalid_token_returned():
    pass


def test_token_successful():
    pass


def test_saml_response():
    token = Token(_protocol='mock://')

    saml_url = 'mock://account.post.ch/SAML/IdentityProvider/'
    sso_url = 'mock://postcardcreator.post.ch/saml/SSO/alias/defaultAlias'

    saml_response = pkg_resources.resource_string(__name__, 'saml_response.html').decode('utf-8')
    access_token = {
        'access_token': 'access_token',
        'token_type': 'token_type',
        'expires_in': 0
    }

    adapter.register_uri('GET', saml_url, text='', reason='')
    adapter.register_uri('POST', saml_url, reason='', text=saml_response)
    adapter.register_uri('POST', sso_url, reason='', text=json.dumps(access_token))

    token.fetch_token('username', 'password')
