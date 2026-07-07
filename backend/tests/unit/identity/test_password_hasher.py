from hiresense.identity.domain import hash_password, verify_password


def test_hash_is_self_describing_scrypt_string() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("scrypt$")
    assert len(encoded.split("$")) == 6


def test_verify_accepts_correct_password() -> None:
    encoded = hash_password("s3cret")
    assert verify_password("s3cret", encoded) is True


def test_verify_rejects_wrong_password() -> None:
    encoded = hash_password("s3cret")
    assert verify_password("nope", encoded) is False


def test_hash_uses_random_salt() -> None:
    # Same password hashed twice yields different strings (unique salts).
    assert hash_password("same") != hash_password("same")


def test_verify_returns_false_on_malformed_hash() -> None:
    assert verify_password("pw", "not-a-valid-hash") is False
    # Well-formed shape but an unsupported scheme name must be rejected.
    unsupported_scheme = "$".join(["unknown", "1", "1", "1", "AAAA", "BBBB"])
    assert verify_password("pw", unsupported_scheme) is False
    assert verify_password("pw", "") is False
