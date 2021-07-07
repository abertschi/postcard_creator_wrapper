# Postcard Creator 

[![PyPI version](https://img.shields.io/pypi/v/postcard_creator.svg)](https://badge.fury.io/py/postcard_creator) [![Build Status](https://travis-ci.org/abertschi/postcard_creator_wrapper.svg?branch=master)](https://travis-ci.org/abertschi/postcard_creator_wrapper) [![codecov](https://codecov.io/gh/abertschi/postcard_creator_wrapper/branch/master/graph/badge.svg)](https://codecov.io/gh/abertschi/postcard_creator_wrapper) [![Codacy Badge](https://api.codacy.com/project/badge/Grade/970d46284d854b11ba4fb0c9cee760c7)](https://www.codacy.com/app/abertschi/postcard_creator_wrapper?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=abertschi/postcard_creator_wrapper&amp;utm_campaign=Badge_Grade) [![PyPI version](https://img.shields.io/pypi/pyversions/postcard_creator.svg)](https://pypi.python.org/pypi/postcard_creator) [![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)

A python wrapper around the Rest API of the Swiss Postcard creator.

## Installation
```sh
# requires python 3.6 or later
$ pip install postcard-creator
```

## Setup / API Usage

```python
from postcard_creator.postcard_creator import PostcardCreator

w = PostcardCreator(token)
w.get_quota()
w.get_user_info()
w.get_billing_saldo()
w.has_free_postcard()
w.send_free_card(postcard=)
```

## Usage

```python
from postcard_creator.postcard_creator import PostcardCreator, Postcard, Token, Recipient, Sender

token = Token()
token.fetch_token(username='', password='')
token.has_valid_credentials(username='', password='')
recipient = Recipient(prename='', lastname='', street='', place='', zip_code=0000)
sender = Sender(prename='', lastname='', street='', place='', zip_code=0000)
card = Postcard(message='', recipient=recipient, sender=sender, picture_stream=open('./my-photo.jpg', 'rb'))

w = PostcardCreator(token)
w.send_free_card(postcard=card, mock_send=False, image_export=False)
```

### Advanced configuration
The following keyword arguments are available for advanced configuration.

**PostcardCreator#send_free_card()**:
- `image_export=False`: Export postcard image to current directory (os.getcwd)
- `mock_send=False`: Do not submit order (testing)

### Logging
```python
import logging

logger = logging.getLogger('postcard_creator')

# log levels
# 5: trace
# 10: debug
# 20: info
# 30: warning
```

## Example
- [Postcards](https://github.com/abertschi/postcards) is a commandline interface built around this library.
- See [tests](./tests/) for more usage examples.

## Test
```sh
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
pytest
```

## Related
- [postcards](https://github.com/abertschi/postcards) - A CLI for the Swiss Postcard Creator
- [postcardcreator](https://github.com/gido/postcardcreator) - node.js API for the Swiss Post Postcard Creator

## Release notes
### v2.2, 2021-07-07
- drop support for postcard_creator_legacy
- update legacy (username/ password) token authentication due to changed endpoints
  - note: legacy method now uses postcard_creator_swissid endpoints instead of postcard_creator_legacy, postcard_creator_legacy is out of life
  
### v2.1, 2021-05-16
- update requests to v2.25.1 to fix "AttributeError: 'NoneType' object has no attribute 'group'" in authentication. #27

### v2.0, 2021-02
- support of new swissid authentication (access_token with code/ code_verifier)
- support of new endpoints at https://pccweb.api.post.ch/secure/api/mobile/v1
- class PostcardCreator is a proxy which instantiates an endpoint wrapper compatible with authentication method of token, underlying wrappers are: PostcardCreatorSwissId, PostcardCreatorLegacy 
- migration to v2.0
  + with authentication method swissid: if you rely on get_billing_saldo(), get_user_info(): these endpoints return data in different format
  + customizations image_target_width, image_target_height, image_quality_factor no longer compatible with authentication method swissid
- require python 3.6 or later

### v1.1, 2020-01-30
- support for swissid authentication
- Method `Token#has_valid_credentials` and `Token#fetch_token` introduce a parameter `method` 
  which can be set to one of these vals: `['mixed', 'legacy', 'swissid']`. `'mixed'` is default and tries both
  authentication procedures 

### v0.0.8, 2018-03-28
- Migrate to postcardcreator API 2.2

### v0.0.7, 2017-12-28
- Fix issues with PNG images [#6](https://github.com/abertschi/postcard_creator_wrapper/pull/6)

### v0.0.6, 2017-11-22
- internal changes
- do not use requirements.txt in setup.py anymore. set all requirements in 
install_requires without explicit version numbers

## Troubleshooting

#### “The headers or library files could not be found for jpeg”
`pip install` fails with the above error. Install libjpeg as discussed here
https://stackoverflow.com/questions/44043906/the-headers-or-library-files-could-not-be-found-for-jpeg-installing-pillow-on


## Author

Andrin Bertschi  
[https://twitter.com/andrinbertschi](https://twitter.com/andrinbertschi)

## License

[Apache License 2.0](LICENSE.md)

<3

