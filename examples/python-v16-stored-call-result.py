"""Inspect CALL → SET → consumer connections without repeating effects.

Open the `dispatch` function graph. Drag the output of CALL calculate
onto CALL deliver's positional arg1 or `label=` input.
The qualified source proposal references the existing `stored` local.
No source code is executed by the visual graph viewer.
"""


def calculate(value):
    return value * 2


def deliver(number, *, label):
    return number


def dispatch(value):
    stored = calculate(value)
    return deliver(0, label='before')
