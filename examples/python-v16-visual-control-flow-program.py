"""Python-first v2.41 control-flow authoring example.

The Branch, For and While functions are equivalent to creating them through
qualified Source Operations from empty function definitions. This file is
*only parsed* during the gate; it is never executed by the analyzer.
"""

def classify(value):
    if value < 0:
        return -1
    return 1


def sum_to(limit):
    total = 0
    for index in range(limit):
        total += index
    return total


def countdown(limit):
    remaining = limit
    steps = 0
    while remaining > 0:
        remaining -= 1
        steps += 1
    return steps


def start():
    return 42


if __name__ == '__main__':
    print(start())
