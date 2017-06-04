# postcard_creator_wrapper
A python wrapper around the Rest API of the Swiss Postcard creator


This project is still in early development. Feedback and support appreciated.

```python
    Debug.debug = True
    Debug.trace = True

    token = Token()
    token.fetch_token(username='', password='')
    recipient = Recipient(prename='', lastname='', street='', place='', zip_code=0000)
    sender = Sender(prename='', lastname='', street='', place='', zip_code=0000)
    card = Postcard(message='', recipient=recipient, sender=sender, picture_location='./asset.jpg')

    w = PostcardCreatorWrapper(token)
    w.send_free_card(postcard=card)
```

## API
```python
    w = PostcardCreatorWrapper(token)
    w.get_user_info()
    w.get_billing_saldo()
    w.get_quota()
    w.has_free_postcard()
    w.send_free_card(postcard=)
    
```
