"""Module-level guarded calls with nested argument expressions.

This file is a parser/visualization fixture, not executed when opened.
Unverified call targets are never treated as statically resolved.
"""


def choose(a, b):
    return a if a > b else b


def nested_expression(a, b, c, d):
    return (a + b) * (c + d)


def early_exit(value):
    if value < 0:
        return None
    return value


if __name__ == '__main__':
    print(choose(3, 9))
    print(nested_expression(1, 2, 3, 4))
    print(early_exit(-1))
