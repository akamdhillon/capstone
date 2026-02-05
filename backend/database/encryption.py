# =============================================================================
# CLARITY+ BACKEND - AES-256-GCM ENCRYPTION
# =============================================================================
"""
Encryption utilities for securing face embeddings at rest.
Uses AES-256-GCM for authenticated encryption.
"""

import json
import os
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import get_settings


def _get_key() -> bytes:
    """
    Get the 32-byte AES-256 encryption key.
    Pads or truncates the configured key to exactly 32 bytes.
    """
    settings = get_settings()
    key = settings.encryption_key.encode('utf-8')
    # Ensure exactly 32 bytes for AES-256
    if len(key) < 32:
        key = key.ljust(32, b'\0')
    elif len(key) > 32:
        key = key[:32]
    return key


def encrypt_embedding(embedding: list[float]) -> Tuple[bytes, bytes, bytes]:
    """
    Encrypt a face embedding using AES-256-GCM.
    
    Args:
        embedding: Face embedding as a list of floats
        
    Returns:
        Tuple of (ciphertext, iv, tag) - all as bytes
        
    Note:
        GCM mode provides both confidentiality and integrity.
        The IV must be unique for each encryption with the same key.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    
    # Generate random 12-byte IV (recommended for GCM)
    iv = os.urandom(12)
    
    # Serialize embedding to JSON bytes
    plaintext = json.dumps(embedding).encode('utf-8')
    
    # Encrypt with authentication
    # GCM produces ciphertext with appended 16-byte tag
    ciphertext_with_tag = aesgcm.encrypt(iv, plaintext, None)
    
    # Split ciphertext and tag (last 16 bytes is tag)
    ciphertext = ciphertext_with_tag[:-16]
    tag = ciphertext_with_tag[-16:]
    
    return ciphertext, iv, tag


def decrypt_embedding(ciphertext: bytes, iv: bytes, tag: bytes) -> list[float]:
    """
    Decrypt a face embedding using AES-256-GCM.
    
    Args:
        ciphertext: Encrypted embedding data
        iv: Initialization vector used during encryption
        tag: Authentication tag for integrity verification
        
    Returns:
        Decrypted face embedding as a list of floats
        
    Raises:
        InvalidTag: If authentication fails (data tampered)
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    
    # Reconstruct ciphertext with tag for decryption
    ciphertext_with_tag = ciphertext + tag
    
    # Decrypt and verify
    plaintext = aesgcm.decrypt(iv, ciphertext_with_tag, None)
    
    # Deserialize back to list
    return json.loads(plaintext.decode('utf-8'))


def verify_key_strength() -> bool:
    """
    Verify that the encryption key meets security requirements.
    Returns True if key is strong enough, False otherwise.
    """
    settings = get_settings()
    key = settings.encryption_key
    
    # Check for default/weak key
    if key == "clarity_default_key_change_in_prod!":
        return False
    
    # Should be at least 32 characters for AES-256
    if len(key) < 32:
        return False
    
    return True
