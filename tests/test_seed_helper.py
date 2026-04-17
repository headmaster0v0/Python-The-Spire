from __future__ import annotations

from sts_py.engine.core.seed import seed_long_to_string, seed_string_to_long, sterilize_seed_string


def test_seed_roundtrip_unsigned():
    # negative values are treated as unsigned 64-bit for string encoding
    vals = [0, 1, 2, 12345, -1, -(1 << 63), -(1 << 62)]
    for v in vals:
        s = seed_long_to_string(v)
        if s == "":
            continue
        v2 = seed_string_to_long(s)
        assert v2 == (v & 0xFFFFFFFFFFFFFFFF)


def test_sterilize_replaces_o():
    assert sterilize_seed_string("o0o") == "000"
    assert sterilize_seed_string("abc123") == "ABC123"
