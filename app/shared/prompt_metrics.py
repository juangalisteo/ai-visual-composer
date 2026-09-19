def estimate_conservative_tokens(
    value: str,
) -> int:
    """Return the project-wide conservative prompt-token estimate."""
    if not value:
        return 0
    return max(
        len(value.split()),
        len(value) // 4,
    )
