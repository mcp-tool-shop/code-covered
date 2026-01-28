"""Sample validator module for testing code-covered."""


def validate_input(data: str) -> bool:
    """Validate input data."""
    if not data:
        return False  # Line 7 - uncovered (if_true_branch)

    if len(data) > 100:
        raise ValueError("Input too long")  # Line 11 - uncovered (raise)

    try:
        int(data)  # Line 14 - uncovered
    except ValueError:
        return False  # Line 16 - uncovered (exception_handler)

    return True


def process(items: list) -> list:
    """Process a list of items."""
    results = []
    for item in items:
        results.append(item.upper())  # Covered
    return results
