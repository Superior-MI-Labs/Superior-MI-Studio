"""Source-backed visual variable bindings, operators, returns and loops."""


def combine_strings():
    a = "a"
    b = "b"
    c = a + b
    return c


def sum_items(items):
    total = 0
    for item in items:
        total += item
    return total


def reassign_example():
    counter = 1
    counter = counter + 2
    return counter


if __name__ == "__main__":
    print(combine_strings())
    print(sum_items([1, 2, 3]))
    print(reassign_example())
