"""Small, source-backed recurrence examples for v0.9 graph inspection."""


def countdown(n: int) -> int:
    while n > 0:
        n -= 1
    return n


def accumulate(items: list[int]) -> int:
    total = 0
    for item in items:
        total += item
    return total


def conditional_countdown(n: int) -> int:
    while n > 0:
        if n > 3:
            n -= 2
        else:
            n -= 1
    return n


if __name__ == '__main__':
    assert countdown(7) == 0
    assert accumulate([1, 2, 3]) == 6
    assert conditional_countdown(7) == 0
    print('v0.9 Python examples PASS')
