"""
Encryption service for E2E encryption utilities.

Note: The actual encryption/decryption happens client-side.
This service provides server-side key management and utilities.
"""

import base64
import os
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


class EncryptionService:
    """
    Encryption utilities for E2E encryption.
    
    This service provides helper functions for encryption operations.
    The actual message encryption happens on the client side.
    Server only stores and forwards encrypted blobs.
    """
    
    @staticmethod
    def generate_key_pair() -> Tuple[str, str]:
        """
        Generate a new X25519 key pair.
        
        Returns:
            Tuple of (private_key_b64, public_key_b64)
            
        Note: This is primarily for testing. In production,
        keys should be generated client-side.
        """
        private_key = X25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize keys
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        
        return (
            base64.b64encode(private_bytes).decode('utf-8'),
            base64.b64encode(public_bytes).decode('utf-8'),
        )
    
    @staticmethod
    def derive_shared_key(
        private_key_b64: str,
        peer_public_key_b64: str,
    ) -> bytes:
        """
        Derive a shared secret from private key and peer's public key.
        
        Uses X25519 key exchange followed by HKDF to derive
        a 256-bit key suitable for AES-GCM.
        
        Args:
            private_key_b64: Base64-encoded private key
            peer_public_key_b64: Base64-encoded peer's public key
            
        Returns:
            32-byte derived key for AES-256-GCM
        """
        private_bytes = base64.b64decode(private_key_b64)
        public_bytes = base64.b64decode(peer_public_key_b64)
        
        private_key = X25519PrivateKey.from_private_bytes(private_bytes)
        peer_public_key = X25519PublicKey.from_public_bytes(public_bytes)
        
        # Perform X25519 key exchange
        shared_secret = private_key.exchange(peer_public_key)
        
        # Derive final key using HKDF
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"messaging-platform-e2e",
        ).derive(shared_secret)
        
        return derived_key
    
    @staticmethod
    def encrypt_message(
        message: str,
        shared_key: bytes,
    ) -> Tuple[str, str]:
        """
        Encrypt a message using AES-256-GCM.
        
        Args:
            message: Plaintext message to encrypt
            shared_key: 32-byte shared key
            
        Returns:
            Tuple of (encrypted_content_b64, nonce_b64)
        """
        aesgcm = AESGCM(shared_key)
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        
        encrypted = aesgcm.encrypt(nonce, message.encode('utf-8'), None)
        
        return (
            base64.b64encode(encrypted).decode('utf-8'),
            base64.b64encode(nonce).decode('utf-8'),
        )
    
    @staticmethod
    def decrypt_message(
        encrypted_content_b64: str,
        nonce_b64: str,
        shared_key: bytes,
    ) -> str:
        """
        Decrypt a message using AES-256-GCM.
        
        Args:
            encrypted_content_b64: Base64-encoded ciphertext
            nonce_b64: Base64-encoded nonce
            shared_key: 32-byte shared key
            
        Returns:
            Decrypted message string
        """
        aesgcm = AESGCM(shared_key)
        
        encrypted = base64.b64decode(encrypted_content_b64)
        nonce = base64.b64decode(nonce_b64)
        
        decrypted = aesgcm.decrypt(nonce, encrypted, None)
        
        return decrypted.decode('utf-8')
    
    @staticmethod
    def validate_public_key(public_key_b64: str) -> bool:
        """
        Validate that a string is a valid base64-encoded X25519 public key.
        
        Args:
            public_key_b64: Base64-encoded public key to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            public_bytes = base64.b64decode(public_key_b64)
            if len(public_bytes) != 32:
                return False
            X25519PublicKey.from_public_bytes(public_bytes)
            return True
        except Exception:
            return False
