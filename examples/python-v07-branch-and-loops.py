"""v0.7 visual programming demo. Safe to inspect; run only if you choose."""


def classify(score: int) -> str:
    if score >= 60:
        bonus = score + 5
        limit = score > 90
        return "distinction" if limit else "pass"
    else:
        deduction = 3
        is_near = score > 40
        return "review" if is_near else "retry"


def count_high(values: list[int]) -> int:
    total = 0
    for value in values:
        if value > 50:
            total += 1
    return total


def reduce_until_small(value: int) -> int:
    while value > 10:
        value -= 2
    return value


if __name__ == '__main__':
    print(classify(85))
    print(count_high([1, 55, 70, 4]))
    print(reduce_until_small(17))
