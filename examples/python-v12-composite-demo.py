"""Real Python code to demonstrate expanded nested source regions."""

def countdown(n: int) -> int:
    while n > 0:
        n -= 1
    return n


def outer(prefix: str):
    def inner(suffix: str):
        return prefix + suffix
    return inner('!')


def choose(value: int) -> int:
    if value > 10:
        return value
    return 10


if __name__ == '__main__':
    print(countdown(3), outer('hello'), choose(4))
