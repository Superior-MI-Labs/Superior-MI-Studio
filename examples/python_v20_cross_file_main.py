"""Inspect real module-level call sites without running code on open.

Copy this file and python_v20_cross_file_helper.py into the same directory,
then enable "Toggle import candidates" in Files / System to inspect the
possible local import edge. An actual runtime import may resolve differently.
"""
from python_v20_cross_file_helper import double


def calculate(value: int) -> int:
    return double(value) + 1


if __name__ == '__main__':
    print(calculate(10))
