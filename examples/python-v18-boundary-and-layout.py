"""Small safe file for testing v1.8 source-boundary editing and layout."""


def choose(a: int, b: int) -> int:
    return a


def nested_expression(a: int, b: int, c: int, d: int) -> int:
    total = ((a + b) * (c + d)) + (a * b)
    return total


def early_exit(value: int) -> int:
    if value < 0:
        return 0
    return value


if __name__ == '__main__':
    print(choose(3, 9))
    print(nested_expression(1, 2, 3, 4))
    print(early_exit(-1))
