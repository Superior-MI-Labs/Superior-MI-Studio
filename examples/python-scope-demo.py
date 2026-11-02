"""Native Node Lab Python source test fixture. Static inspection only."""

tax: int = 2

def outer(base: int) -> int:
    increment = 10

    def inner(value: int) -> int:
        result = base + increment + value + tax
        return result

    return inner(5)


def square_plus_ten(a: int) -> int:
    total = a * a
    return total + 10

class Calculator:
    factor: int = 3

    def calculate(self, x: int) -> int:
        return x * self.factor

if __name__ == '__main__':
    print('outer(5) =', outer(5))
    print('square_plus_ten(3) =', square_plus_ten(3))
