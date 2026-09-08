from user_api import create_user


def register(payload):
    return create_user({"name": payload["name"], "email": payload["email"]})
