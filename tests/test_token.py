from postcard_creator.postcard_creator import PostcardCreator, Token, Postcard, Sender, Recipient, \
    PostcardCreatorException
import requests
import requests_mock
import logging
import pkg_resources
import json
import pytest
import os

logging.basicConfig(level=logging.INFO,
                    format='%(name)s (%(levelname)s): %(message)s')
logging.getLogger('postcard_creator').setLevel(10)

URL_TOKEN_SAML = 'mock://account.post.ch/SAML/IdentityProvider/'
URL_TOKEN_SSO = 'mock://postcardcreator.post.ch/saml/SSO/alias/defaultAlias'
URL_PCC_HOST = 'mock://postcardcreator.post.ch/rest/2.1'

adapter_token = None
adapter_pcc = None


def create_mocked_session(self):
    global adapter_token
    session = requests.Session()
    session.mount('mock', adapter_token)
    return session


def create_token():
    global adapter_token
    adapter_token = requests_mock.Adapter()
    Token._create_session = create_mocked_session
    return Token(_protocol='mock://')


def create_postcard_creator():
    global adapter_pcc
    adapter_pcc = requests_mock.Adapter()
    PostcardCreator._create_session = create_mocked_session
    token = create_token()
    token.token_expires_in = 3600
    token.token_type = 'Bearer'
    token.token = 0
    return PostcardCreator(token=token, _protocol='mock://')


def create_token_with_successful_login():
    token = create_token()
    saml_response = pkg_resources.resource_string(__name__, 'saml_response.html').decode('utf-8')
    access_token = {
        'access_token': 0,
        'token_type': 'token_type',
        'expires_in': 3600
    }

    adapter_token.register_uri('GET', URL_TOKEN_SAML, text='', reason='')
    adapter_token.register_uri('POST', URL_TOKEN_SAML, reason='', text=saml_response)
    adapter_token.register_uri('POST', URL_TOKEN_SSO, reason='', text=json.dumps(access_token))
    return token


def test_token_invalid_args():
    with pytest.raises(PostcardCreatorException):
        token = create_token()
        token.fetch_token(None, None)


def test_token_wrong_user_credentials():
    token = create_token()
    adapter_token.register_uri('GET', URL_TOKEN_SAML, text='', reason='', status_code=500)
    adapter_token.register_uri('POST', URL_TOKEN_SAML, reason='', text='')
    adapter_token.register_uri('POST', URL_TOKEN_SSO, reason='', text='')

    with pytest.raises(PostcardCreatorException):
        token.fetch_token('username', 'password')


def test_token_saml_invalid_response():
    token = create_token_with_successful_login()
    saml_response = pkg_resources.resource_string(__name__, 'saml_response_invalid.html').decode('utf-8')
    adapter_token.register_uri('POST', URL_TOKEN_SAML, reason='', text=saml_response)

    with pytest.raises(PostcardCreatorException):
        token.fetch_token('username', 'password')


def test_token_invalid_token_returned():
    token = create_token_with_successful_login()
    adapter_token.register_uri('POST', URL_TOKEN_SSO, reason='', text=json.dumps(''), status_code=500)

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


def test_pcc_send_free_card_successful():

    # work in progress
    pcc = create_postcard_creator()
    sender = Sender(prename='prename',
                    lastname='lastname',
                    street='My street 11',
                    place='place',
                    zip_code=8000)

    recipient = Recipient(prename='prename',
                          lastname='lastname',
                          street='My street 11',
                          place='place',
                          zip_code=8000)

    file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'asset.jpg')
    postcard = Postcard(sender=sender,
                        recipient=recipient,
                        picture_stream=open(file, 'rb'),
                        message='Coding rocks!')

    userId = 1381204
    user = {
        'tenantId': 'CHE',
        'userId': userId,
        'email': 'hi@foo.ch',
        'sex': 'FEMALE',
        'givenName': 'Kukka',
        'familyName': 'Meier',
        'address': 'My adress 22',
        'postCode': '5391',
        'place': 'Zurich',
        'country': 'CHE',
        'language': 'en',
        'newsletterSubscribed': False,
        'gtcAccepted': True
    }
    quota = {
        'available': True,
        'next': '2017-07-29',
        'quota': -1,
        'retentionDays': 1

    }
    mailingId = 28661786
    mailing_headers = {
        'Location': 'https://postcardcreator.post.ch/rest/2.1/users/{}/mailings/{}'.format(userId, mailingId)
    }

    mailings = {
        'name': 'Mobile App Mailing 2017-06-20 09:04',
        'addressFormat': 'PERSON_FIRST',
        'paid': False
    }

    URL_USERS_CURRENT = URL_PCC_HOST + '/users/current'
    URL_USERS_QUOTA = URL_PCC_HOST + '/users/{}/quota'.format(userId)
    URL_USERS_MAILINGS = URL_PCC_HOST + '/users/{}/mailings'.format(userId)

    adapter_pcc.register_uri('GET', URL_USERS_CURRENT, reason='', text=json.dumps(user))
    adapter_pcc.register_uri('GET', URL_USERS_QUOTA, reason='', text=json.dumps(quota))
    adapter_pcc.register_uri('POST', URL_USERS_MAILINGS,
                             reason='', text=json.dumps(mailings), headers=mailing_headers)

    #pcc.send_free_card(postcard)
