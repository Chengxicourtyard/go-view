import random
import string

from flask import session

CAPTCHA_SESSION_KEY = "login_captcha"


def generate_captcha(length: int = 4) -> str:
    code = "".join(random.choices(string.digits, k=length))
    session[CAPTCHA_SESSION_KEY] = code
    return code


def verify_captcha(value: str) -> bool:
    expected = session.pop(CAPTCHA_SESSION_KEY, None)
    if not expected or not value:
        return False
    return value.strip() == expected


def current_captcha() -> str:
    code = session.get(CAPTCHA_SESSION_KEY)
    if not code:
        code = generate_captcha()
    return code
