"""Safe example for visual inspection. Use a separate editable copy for edits."""

THRESHOLD: int = 10


def grade(score: int) -> str:
    if score >= THRESHOLD:
        result = "pass"
    elif score >= 5:
        result = "review"
    else:
        result = "fail"
    return result


def adjusted_count(value: int) -> int:
    if value > THRESHOLD:
        result = value + 2
    else:
        result = value - 2
    return result


def pending_complex_example(values: list[int]) -> int:
    total = 0
    for item in values:
        total += item
    return total


if __name__ == '__main__':
    print(grade(12))
    print(adjusted_count(8))
