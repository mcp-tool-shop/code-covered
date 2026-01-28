"""Golden fixture source file for MCP tool testing."""


def validate(data):
    if data is None:
        return False
    if not isinstance(data, dict):
        raise ValueError("data must be dict")
    return True


def process(items):
    for item in items:
        yield item * 2
