"""Open as Python Source Graph, then expand each IF and loop region.

Expected readable representation: variable bindings, FOR/IF controls,
compact + and +=/-= operators, graph boundary interfaces, and returns.
"""

def accumulate(items: list[int]) -> int:
    total = 0
    for item in items:
        if item > 0:
            total += item
        else:
            total -= 2
    return total


def categorize(score: int) -> str:
    if score > 90:
        label = 'high'
    elif score > 60:
        label = 'medium'
    else:
        label = 'low'
    return label


def count_down(n: int) -> int:
    while n > 0:
        n -= 1
    return n


if __name__ == '__main__':
    print(accumulate([2, -4, 3]))
    print(categorize(70))
    print(count_down(3))
