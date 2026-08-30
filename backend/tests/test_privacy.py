"""Tests for PII masking helpers."""

from app.core.privacy import mask_pan


def test_mask_pan():
    assert mask_pan("ABCDE1234F") == "ABCXX1234X"


def test_mask_pan_short_value():
    assert mask_pan("ABC") == "ABC"
