"""
JWT decoding helper.

Used to validate auth tokens forwarded from the frontend before serving
sensitive endpoints. The HMAC-SHA256 secret is expected to be supplied by
the caller; it is intentionally not bound to a module-level constant so
that the secret stays out of source control.
"""

import jwt
from jwt import PyJWKClient, ExpiredSignatureError, InvalidTokenError


def decode_token(token: str, secret_key: str) -> dict:
    """
    Decode and validate a JWT signed with HS256.

    Args:
        token:      The encoded JWT to decode.
        secret_key: The shared HMAC secret used to verify the signature.

    Returns:
        The token payload as a dict on success, or a dict containing an
        ``error`` key describing why decoding failed.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload

    except ExpiredSignatureError:
        # Token is well-formed and validly signed but past its `exp` claim.
        return {"error": "Token has expired"}

    except InvalidTokenError:
        # Catch-all for malformed tokens, bad signatures, etc.
        return {"error": "Invalid token"}


# Example usage:
# secret_key = config['SECRET_KEY']
# token = "jwt_token"
# decoded_payload = decode_token(token, secret_key)
# print(decoded_payload)
