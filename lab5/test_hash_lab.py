from __future__ import annotations

import hashlib

import pytest

from hash_lab import (
    expected_birthday_trials,
    find_truncated_collision,
    sha256_digest,
    sha256_hex,
    truncated_hash_bits,
    verify_truncated_collision,
)


def test_sha256_matches_hashlib() -> None:
    data = b"test vector"
    assert sha256_digest(data) == hashlib.sha256(data).digest()
    assert sha256_hex(data) == hashlib.sha256(data).hexdigest()


def test_truncated_full_256() -> None:
    data = b"x"
    full = int.from_bytes(hashlib.sha256(data).digest(), "big")
    assert truncated_hash_bits(data, 256) == full


def test_truncated_8_is_high_byte() -> None:
    data = b"abc"
    h = hashlib.sha256(data).digest()
    high_byte = h[0]
    assert truncated_hash_bits(data, 8) == high_byte


def test_truncated_consistent() -> None:
    assert truncated_hash_bits(b"m", 24) == truncated_hash_bits(b"m", 24)


def test_truncated_invalid_bits() -> None:
    with pytest.raises(ValueError):
        truncated_hash_bits(b"a", 0)
    with pytest.raises(ValueError):
        truncated_hash_bits(b"a", 257)


def test_find_collision_small_space() -> None:
    """8 бит — ожидаемо ~19 сообщений до коллизии; должно уложиться быстро."""
    a, b, n, val = find_truncated_collision(8, max_trials=50_000)
    assert a != b
    assert verify_truncated_collision(a, b, 8)
    assert truncated_hash_bits(a, 8) == val == truncated_hash_bits(b, 8)
    assert n < 50_000


def test_verify_collision_false_equal_messages() -> None:
    assert verify_truncated_collision(b"x", b"x", 16) is False


def test_expected_birthday_order() -> None:
    """Для 16 бит ожидание порядка 2^8 * const ≈ сотни."""
    e16 = expected_birthday_trials(16)
    assert 200 < e16 < 400
    e20 = expected_birthday_trials(20)
    assert e20 > e16
