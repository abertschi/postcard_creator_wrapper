import responses
from postcard_creator.postcard_creator import PostcardCreator, Debug, Token, Postcard
import pytest

TOKEN_AUTH_BASE_URL = 'https://account.post.ch'
ACCOUNT_BASE_URL = Token.base
import pkg_resources

#
# response1 = session.get(url=url + query, headers=self.headers)
# Debug.trace_request(response1)
# Debug.log(f' get {url}')
#
# response2 = session.post(url=url + query, headers=self.headers, data=data)
# Debug.trace_request(response2)
# Debug.log(f' post {url}')
#
# response3 = session.post(url=url + query, headers=self.headers)
# Debug.trace_request(response3)
# Debug.log(f' post {url}')


@pytest.fixture
def ppc_wrapper():
    # username = 'test_username'
    # password = 'test_password'
    # return Token(token)
    return None


def test_saml_response():
    url_identitiy_provider = f'{TOKEN_AUTH_BASE_URL}/SAML/IdentityProvider/'
    query = '?login&app=pcc&service=pcc&targetURL=https%3A%2F%2Fpostcardcreator.post.ch&abortURL=https%3A%2F%2Fpostcardcreator.post.ch&inMobileApp=true'

    username = 'test_username'
    password = 'test_password'

    data = {
        'isiwebuserid': username,
        'isiwebpasswd': password,
        'confirmLogin': ''
    }
    saml_response = pkg_resources.resource_string(__name__, 'saml_response.html').decode('utf-8')

    with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
        rsps.add(responses.GET, url_identitiy_provider + query,
                 body={'junk of not important html'}, status=200)

        rsps.add(responses.POST, url_identitiy_provider + query,
                 body={'junk of not important html'}, status=200)

        rsps.add(responses.POST, url_identitiy_provider + query,
                 body={saml_response}, status=200)
        token = Token()
        token.fetch_token(username, password)
