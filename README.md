# Postcard Creator [![PyPI version](https://img.shields.io/pypi/v/postcard_creator.svg)](https://badge.fury.io/py/postcard_creator) [![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A python wrapper around the Rest API of the Swiss Postcard creator  
This project is still in early development. Feedback and support appreciated.

## Installation
```sh
$ pip install postcard-creator
```

## Setup / API Usage
```python
from postcard_creator.postcard_creator import PostcardCreator

w = PostcardCreator(token)
w.get_user_info()
w.get_billing_saldo()
w.get_quota()
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
card = Postcard(message='', recipient=recipient, sender=sender, picture_location='./asset.jpg')

w = PostcardCreator(token)
w.send_free_card(postcard=card, mock_send=False)
```
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

## Related
- [postcards](https://github.com/abertschi/postcards) - A CLI for the Swiss Postcard Creator
- [postcardcreator](https://github.com/gido/postcardcreator) - JavaScript API wrapper

## Author

Andrin Bertschi

## License

[Apache License 2.0](LICENSE.md) © Andrin Bertschi
