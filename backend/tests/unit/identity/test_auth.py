from datetime import datetime, timezone

from hiresense.identity.domain import AuthService, hash_password


def test_token_expiry_reflects_configured_hours() -> None:
    service = AuthService(
        username="admin", password="secret", jwt_secret="key", expiry_hours=1
    )
    token = service.login("admin", "secret")
    assert token is not None
    payload = service.validate_token(token)
    assert payload is not None
    lifetime = payload["exp"] - int(datetime.now(timezone.utc).timestamp())
    # ~1h window; allow slack for clock/execution time.
    assert 3000 < lifetime <= 3600


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


def test_token_carries_default_admin_role() -> None:
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    token = service.login("admin", "secret")
    assert token is not None
    payload = service.validate_token(token)
    assert payload is not None
    assert payload["role"] == "admin"


def test_token_carries_configured_role() -> None:
    service = AuthService(username="bob", password="secret", jwt_secret="key", role="member")
    token = service.login("bob", "secret")
    assert token is not None
    payload = service.validate_token(token)
    assert payload is not None
    assert payload["role"] == "member"


def test_login_with_password_hash_accepts_correct_password() -> None:
    service = AuthService(
        username="admin",
        password="",
        jwt_secret="key",
        password_hash=hash_password("secret"),
    )
    assert service.login("admin", "secret") is not None


def test_login_with_password_hash_rejects_wrong_password() -> None:
    service = AuthService(
        username="admin",
        password="",
        jwt_secret="key",
        password_hash=hash_password("secret"),
    )
    assert service.login("admin", "wrong") is None


def test_password_hash_takes_precedence_and_plaintext_not_retained() -> None:
    ignored_plaintext = "wrong-value"
    service = AuthService(
        username="admin",
        password=ignored_plaintext,
        jwt_secret="key",
        password_hash=hash_password("secret"),
    )
    # Plaintext arg is ignored when a hash is present, and not kept in the field.
    assert service.login("admin", ignored_plaintext) is None
    assert service.login("admin", "secret") is not None
    assert service._password == ""


def test_login_rejects_wrong_username() -> None:
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    assert service.login("attacker", "secret") is None


def test_login_rejects_when_no_credential_configured() -> None:
    # A fully-blank credential must never authenticate.
    service = AuthService(username="", password="", jwt_secret="key")
    assert service.login("", "") is None


def test_login_handles_non_ascii_input_without_error() -> None:
    # compare_digest raises TypeError on non-ASCII str; the service must return a
    # clean auth failure (None), not propagate an exception (500).
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    assert service.login("admín", "sécret") is None
