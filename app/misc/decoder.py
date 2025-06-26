import jwt
from jwt import PyJWKClient, ExpiredSignatureError, InvalidTokenError

def decode_token(token: str, secret_key: str) -> dict:
    try:
        # Decode the JWT token
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])

        return payload
    
    except ExpiredSignatureError:
        # Handle the case where the token is expired
        return {"error": "Token has expired"}
    
    except InvalidTokenError:
        # Handle the case where the token is invalid
        return {"error": "Invalid token"}

# secret_key = config['SECRET_KEY']  # Replace this with your actual secret key
# token = "jwt_token"  # Replace this with the actual token
# decoded_payload = decode_jwt(token, secret_key)
# print(decoded_payload)
