import base64
import hashlib

from cryptography.fernet import Fernet

from config import Config


def _fernet() -> Fernet:
    digest = hashlib.sha256(Config.ENCRYPTION_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(cipher: str) -> str:
    if not cipher:
        return ""
    return _fernet().decrypt(cipher.encode()).decode()
