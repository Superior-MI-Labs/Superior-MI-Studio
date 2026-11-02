"""Real source file for v1.5 compact composite/function/loop qualification."""

def accumulate(items: list[int]) -> int:
    total = 0
    for item in items:
        if item > 0:
            total += item
    return total


def countdown(value: int) -> int:
    while value > 10:
        value -= 2
    return value


def nested(rows):
    count = 0
    for row in rows:
        for item in row:
            if item < 0:
                continue
            count += item
    return count


if __name__ == '__main__':
    print(accumulate([1, -4, 3]), countdown(18), nested([[1, -2], [3]]))
