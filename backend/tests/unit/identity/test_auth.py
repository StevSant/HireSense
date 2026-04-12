from hiresense.identity.domain import AuthService


def test_verify_valid_credentials() -> None:
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    token = service.login("admin", "secret")
    assert token is not None
    assert isinstance(token, str)


def test_verify_invalid_credentials() -> None:
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    token = service.login("admin", "wrong")
    assert token is None


def test_validate_token() -> None:
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    token = service.login("admin", "secret")
    assert token is not None
    payload = service.validate_token(token)
    assert payload is not None
    assert payload["sub"] == "admin"


def test_validate_invalid_token() -> None:
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    payload = service.validate_token("garbage.token.here")
    assert payload is None
