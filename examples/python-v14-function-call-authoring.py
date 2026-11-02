"""Safe source-backed call construction examples (not executed by the viewer).

Open this file as a Python graph and select Source operations. A qualified
Call → Return can replace `pass` in `dispatch`; Call → Continue can insert a
statement before `return` in `inspect`. Both ask for a source parameter and a
uniquely defined module function, then show a diff before saving.
"""


def choose(left: int, right: int) -> int:
    return left if left >= right else right


def double(number: int) -> int:
    return number * 2


def dispatch(value: int) -> int:
    pass


def inspect(value: int) -> int:
    return value
