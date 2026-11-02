"""Native graph-surface navigation fixture: source stays authoritative."""

def countdown(value: int) -> int:
    while value > 0:
        value -= 1
    return value


def outer(base: int) -> int:
    multiplier = 2

    def middle(offset: int) -> int:
        def inner(value: int) -> int:
            result = value + offset
            return result * multiplier

        return inner(base)

    return middle(3)


if __name__ == '__main__':
    print(countdown(5), outer(4))
