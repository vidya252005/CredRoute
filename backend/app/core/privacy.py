"""PII handling helpers for API responses."""


def mask_pan(pan: str | None) -> str | None:
    """Mask PAN for API responses: ABCDE1234F → ABCXX1234X."""
    if not pan or len(pan) < 10:
        return pan
    return f"{pan[:3]}XX{pan[5:9]}X"
