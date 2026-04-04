"""
Tests for utils/encryption.py — API key encryption, password hashing.
"""


from utils.encryption import (
    decrypt_api_keys,
    decrypt_value,
    derive_key_from_password,
    encrypt_api_keys,
    encrypt_value,
    get_encryption_key,
    hash_password,
    verify_password,
)


class TestEncryptDecrypt:
    """Tests for encrypt_value / decrypt_value roundtrip."""

    def test_roundtrip(self):
        """Encrypt then decrypt returns original value."""
        original = "my-secret-api-key-12345"
        assert decrypt_value(encrypt_value(original)) == original

    def test_empty_input_encrypt(self):
        """Encrypting empty string returns empty string."""
        assert encrypt_value("") == ""

    def test_empty_input_decrypt(self):
        """Decrypting empty string returns empty string."""
        assert decrypt_value("") == ""

    def test_none_like_encrypt(self):
        """Encrypting None-like falsy values returns empty."""
        assert encrypt_value("") == ""

    def test_invalid_ciphertext_returns_empty(self):
        """Decrypting garbage returns empty string, not an exception."""
        assert decrypt_value("not-valid-ciphertext-at-all") == ""

    def test_different_values_produce_different_ciphertexts(self):
        """Two different plaintexts must produce different ciphertexts."""
        ct1 = encrypt_value("key_one")
        ct2 = encrypt_value("key_two")
        assert ct1 != ct2

    def test_same_value_produces_different_ciphertexts(self):
        """Fernet uses random IV — same plaintext → different ciphertext each time."""
        ct1 = encrypt_value("same_key")
        ct2 = encrypt_value("same_key")
        assert ct1 != ct2  # Different due to random IV

    def test_long_value_roundtrip(self):
        """Long API key-like string survives roundtrip."""
        long_key = "a" * 256
        assert decrypt_value(encrypt_value(long_key)) == long_key

    def test_special_characters_roundtrip(self):
        """Values with special chars survive roundtrip."""
        special = "sk-proj-abc123!@#$%^&*()_+-=[]{}|;':\",./<>?"
        assert decrypt_value(encrypt_value(special)) == special


class TestDeriveKey:
    """Tests for derive_key_from_password."""

    def test_returns_bytes(self):
        result = derive_key_from_password("some-password")
        assert isinstance(result, bytes)

    def test_deterministic_with_same_salt(self):
        """Same password + same salt → same key."""
        salt = b"test-salt"
        k1 = derive_key_from_password("password", salt=salt)
        k2 = derive_key_from_password("password", salt=salt)
        assert k1 == k2

    def test_different_passwords_different_keys(self):
        salt = b"test-salt"
        k1 = derive_key_from_password("password1", salt=salt)
        k2 = derive_key_from_password("password2", salt=salt)
        assert k1 != k2

    def test_key_length_valid_for_fernet(self):
        """Fernet requires exactly 44 URL-safe base64 chars."""
        key = derive_key_from_password("any-password")
        assert len(key) == 44


class TestGetEncryptionKey:
    """Tests for get_encryption_key."""

    def test_returns_bytes(self):
        key = get_encryption_key()
        assert isinstance(key, bytes)

    def test_uses_env_var_when_set(self, monkeypatch):
        """44-char env key is used as-is."""
        fake_key = "A" * 44
        monkeypatch.setenv("ENCRYPTION_KEY", fake_key)
        key = get_encryption_key()
        assert key == fake_key.encode()

    def test_derives_key_from_short_env_var(self, monkeypatch):
        """Short env key is derived via PBKDF2."""
        monkeypatch.setenv("ENCRYPTION_KEY", "short-key")
        key = get_encryption_key()
        assert isinstance(key, bytes)
        assert len(key) == 44


class TestPasswordHashing:
    """Tests for hash_password / verify_password."""

    def test_verify_correct_password(self):
        pw = "super-secure-password-123"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_is_not_plaintext(self):
        pw = "my-password"
        hashed = hash_password(pw)
        assert pw not in hashed

    def test_same_password_different_hashes(self):
        """Random salt means same password hashes differently each time."""
        pw = "same-password"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2

    def test_verify_bad_hash_returns_false(self):
        """Corrupted hash should return False, not raise."""
        assert verify_password("any-password", "not-a-valid-hash") is False

    def test_verify_empty_hash_returns_false(self):
        assert verify_password("any-password", "") is False


class TestApiKeyHelpers:
    """Tests for encrypt_api_keys / decrypt_api_keys."""

    def test_encrypt_adds_suffix(self):
        keys = {"finnhub_api_key": "abc123", "alpaca_key": "xyz789"}
        result = encrypt_api_keys(keys)
        assert "finnhub_api_key_encrypted" in result
        assert "alpaca_key_encrypted" in result
        assert "finnhub_api_key" not in result

    def test_decrypt_removes_suffix(self):
        keys = {"finnhub_api_key": "abc123", "alpaca_key": "xyz789"}
        encrypted = encrypt_api_keys(keys)
        decrypted = decrypt_api_keys(encrypted)
        assert decrypted["finnhub_api_key"] == "abc123"
        assert decrypted["alpaca_key"] == "xyz789"

    def test_full_roundtrip(self):
        original = {
            "finnhub_api_key": "fh_test_key",
            "alpaca_api_key": "pk_test_123",
            "alpaca_secret": "sk_test_456",
            "gemini_api_key": "AI_test_789",
        }
        encrypted = encrypt_api_keys(original)
        decrypted = decrypt_api_keys(encrypted)
        for k, v in original.items():
            assert decrypted[k] == v

    def test_skips_already_encrypted_keys(self):
        """Keys ending in _encrypted are not double-encrypted."""
        keys = {"some_key_encrypted": "already_encrypted_value"}
        result = encrypt_api_keys(keys)
        assert result == {}

    def test_skips_empty_values(self):
        keys = {"finnhub_api_key": "", "alpaca_key": "real_value"}
        result = encrypt_api_keys(keys)
        assert "finnhub_api_key_encrypted" not in result
        assert "alpaca_key_encrypted" in result

    def test_empty_dict(self):
        assert encrypt_api_keys({}) == {}
        assert decrypt_api_keys({}) == {}
