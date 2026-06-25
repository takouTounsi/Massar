from __future__ import annotations

import base64
import binascii
import json
import os
from datetime import UTC, datetime
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field


class EncryptedPayload(BaseModel):
    encrypted: bool = True
    algorithm: str = "AES-256-GCM"
    key_id: str
    nonce: str
    ciphertext: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DataEncryptor:
    def __init__(self, key: str, *, key_id: str = "local-dev-key-v1") -> None:
        self.key_id = key_id
        self._key = self._decode_key(key)
        self._aesgcm = AESGCM(self._key)

    @staticmethod
    def generate_key() -> str:
        return base64.b64encode(os.urandom(32)).decode("ascii")

    @staticmethod
    def _decode_key(key: str) -> bytes:
        try:
            decoded = base64.b64decode(key, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("DATA_ENCRYPTION_KEY must be base64-encoded") from exc
        if len(decoded) != 32:
            raise ValueError("DATA_ENCRYPTION_KEY must decode to exactly 32 bytes")
        return decoded

    def encrypt_json(self, payload: Any, *, aad: str | None = None) -> EncryptedPayload:
        nonce = os.urandom(12)
        plaintext = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, self._aad(aad))
        return EncryptedPayload(
            key_id=self.key_id,
            nonce=base64.b64encode(nonce).decode("ascii"),
            ciphertext=base64.b64encode(ciphertext).decode("ascii"),
        )

    def decrypt_json(self, envelope: EncryptedPayload | dict[str, Any], *, aad: str | None = None) -> Any:
        payload = envelope if isinstance(envelope, EncryptedPayload) else EncryptedPayload.model_validate(envelope)
        if payload.algorithm != "AES-256-GCM":
            raise ValueError(f"Unsupported encryption algorithm: {payload.algorithm}")
        try:
            nonce = base64.b64decode(payload.nonce, validate=True)
            ciphertext = base64.b64decode(payload.ciphertext, validate=True)
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, self._aad(aad))
        except (InvalidTag, ValueError) as exc:
            raise ValueError("Encrypted payload could not be decrypted") from exc
        return json.loads(plaintext.decode("utf-8"))

    @staticmethod
    def _aad(value: str | None) -> bytes | None:
        return value.encode("utf-8") if value else None
