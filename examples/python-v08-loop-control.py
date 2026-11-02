"""v0.8 source graph test: no runtime activity when merely opened by Studio.

Open as Python Source Graph; focus scan(), countdown(), nested_loops().
These are real Python functions, NOT a new node interpreter.
"""


def scan(values: list[int]) -> int:
    total = 0
    for value in values:
        if value < 0:
            continue
        if value == 99:
            break
        total += value
    else:
        total += 100
    return total


def countdown(n: int) -> int:
    while n > 0:
        if n == 2:
            break
        n -= 1
    else:
        n = -1
    return n


def nested_loops(rows: list[list[int]]) -> int:
    count = 0
    for row in rows:
        for item in row:
            if item == 0:
                break
            count += 1
    return count


if __name__ == '__main__':
    print('scan normal', scan([1, -1, 2]))  # 103
    print('scan break', scan([1, 99, 2]))   # 1
    print('countdown break', countdown(4))  # 2
    print('countdown complete', countdown(1))  # -1
    print('nested', nested_loops([[1, 0, 3], [5, 6]]))  # 3
