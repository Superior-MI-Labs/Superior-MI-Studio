"""Small real Python file for exercising qualified visual-source builders.

Open in the Python Source Graph and use Node Library -> Source operations.
Choose a builder and review the proposed diff before saving. No code in this
file is executed by the graph viewer.
"""


def identity(value):
    return value


def constant_result():
    return 5


def unfinished(value):
    """A standalone placeholder for the qualified Return builder."""
    pass
