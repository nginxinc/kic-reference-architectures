import base64
from passlib.hash import apr_md5_crypt


def create_secret(user:str , password: str) -> str:
    ciphertext_pass = apr_md5_crypt.using(salt_size=8).hash(password)
    return f"{user}:{ciphertext_pass}"


def create_b64encoded_secret(user: str, password: str) -> str:
    secret = create_secret(user, password)
    return str(base64.b64encode(bytes(secret, "utf-8"), None), "utf-8")