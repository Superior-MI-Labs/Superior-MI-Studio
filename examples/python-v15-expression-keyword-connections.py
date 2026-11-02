"""Source-backed expression and named keyword connection qualification.

Do not execute this file to inspect its visual graph. Open it through Node Lab.
Build a wire from the numeric operator output into the positional CALL input,
or from the value parameter to the CALL label= keyword input. The editor
must propose a reviewed source diff before changing anything on disk.
"""


def deliver(number, *, label, priority):
    return f"{label}: {number} (priority {priority})"


def compose(value):
    arithmetic = 2 + 3 * 4
    comparison = (4 + 5) > 7
    return deliver(0, label="before", priority=1)
