from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import json

from cryptography.fernet import Fernet


def get_cipher():
    key=settings.GOOGLE_TOKEN_ENCRYPTION_KEY
    
    if not key:
        raise ImproperlyConfigured(
            "SET GOOGLE_TOKEN_ENCRYPTION_KEY in .env."
        )
    return Fernet(key.encode("utf-8"))

def encrypt_json(data):
    plaintext = json.dumps(data).encode("utf-8")

    ciphertext = get_cipher().encrypt(plaintext)

    return ciphertext.decode("utf-8")


def decrypt_json(ciphertext):
    plaintext = get_cipher().decrypt(
        ciphertext.encode("utf-8")
    )

    return json.loads(plaintext.decode("utf-8"))