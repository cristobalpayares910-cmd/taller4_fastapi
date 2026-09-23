"""Pruebas de hashing de contrasenas y emision/validacion de JWT."""

import os
import sys
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class PasswordTests(unittest.TestCase):
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("Recicla2026")
        self.assertNotIn("Recicla2026", hashed)

    def test_verify_accepts_correct_password(self):
        self.assertTrue(verify_password("Recicla2026", hash_password("Recicla2026")))

    def test_verify_rejects_wrong_password(self):
        self.assertFalse(verify_password("otra-clave", hash_password("Recicla2026")))

    def test_verify_rejects_corrupted_hash(self):
        self.assertFalse(verify_password("Recicla2026", "hash-invalido"))


class TokenTests(unittest.TestCase):
    def test_roundtrip_returns_subject(self):
        token = create_access_token(42)
        self.assertEqual(decode_access_token(token)["sub"], "42")

    def test_rejects_tampered_token(self):
        token = create_access_token(42)
        with self.assertRaises(TokenError):
            decode_access_token(token + "x")

    def test_rejects_expired_token(self):
        expired = create_access_token(1, expires_minutes=-1)
        with self.assertRaises(TokenError):
            decode_access_token(expired)

    def test_expiration_is_configurable(self):
        payload = decode_access_token(create_access_token(7, expires_minutes=5))
        self.assertIn("exp", payload)


if __name__ == "__main__":
    unittest.main()
