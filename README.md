# Postcard Creator [![PyPI version](https://badge.fury.io/py/postcard_creator.svg)](https://badge.fury.io/py/postcard_creator) [![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A python wrapper around the Rest API of the Swiss Postcard creator  
This project is still in early development. Feedback and support appreciated.

## Installation
```sh
$ pip install postcard_creator
```

## Setup / API Usage
```python
w = PostcardCreator(token)
w.get_user_info()
w.get_billing_saldo()
w.get_quota()
w.has_free_postcard()
w.send_free_card(postcard=)
```

## Usage

```python
Debug.debug = True
Debug.trace = True

token = Token()
token.fetch_token(username='', password='')
recipient = Recipient(prename='', lastname='', street='', place='', zip_code=0000)
sender = Sender(prename='', lastname='', street='', place='', zip_code=0000)
card = Postcard(message='', recipient=recipient, sender=sender, picture_location='./asset.jpg')

w = PostcardCreator(token)
w.send_free_card(postcard=card)
```
## Varia
Looking for an implementation in JavaScript?
- Check out https://github.com/gido/postcardcreator by Gilles Doge (MIT) 

## Author

Andrin Bertschi

## License

[Apache License 2.0](LICENSE.md) © Andrin Bertschi
