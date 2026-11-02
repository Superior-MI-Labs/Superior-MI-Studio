"""Source-backed examples for qualified visual expression creation.

These functions deliberately contain simple source anchors. Node Library,
right-click search, and dragging an eligible PARAMETER output should discover
adapter-qualified actions. They never execute until explicitly invoked.
"""


def arithmetic_placeholder(value: int) -> int:
    """Select the value pin and create `return value + 2`, `-`, or `*`."""
    pass


def comparison_guard(value: int) -> int:
    """Create `if value < 0: return None` before the existing Return."""
    return value


def preserved_result(value):
    """Existing is-None builder and source Return identities remain valid."""
    return value
