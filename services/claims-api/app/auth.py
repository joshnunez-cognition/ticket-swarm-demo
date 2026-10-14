from fastapi import Header, HTTPException

# Demo tokens only. Real deployments use the identity gateway.
TOKENS = {
    "token-alice": {"user_id": "m-100", "role": "member"},
    "token-bob": {"user_id": "m-200", "role": "member"},
    "token-adjuster": {"user_id": "adj-1", "role": "adjuster"},
}


def current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    user = TOKENS.get(token)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return user
