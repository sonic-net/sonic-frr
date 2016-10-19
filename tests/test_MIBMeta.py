import os
import sys

modules_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(modules_path, 'src'))

from unittest import TestCase
from ax_interface import MIBMeta, ValueType


# class TestMIB(TestCase):
#     def test_bad_mib(self):
#         # TODO: finish
#         def handler():
#             pass
#
#         class BadMIB1(metaclass=MIBMeta, prefix='2'):
#             bad_value = '1', ValueType.INTEGER, None
#
#         class BadMIB2(metaclass=MIBMeta, prefix='3'):
#             bad_value = '1', None, handler


"""
>>> keys
[(1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 4), (1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 2), (1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 5)]
>>> three = (1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 3)
>>> bisect.bisect(keys, three)
2
>>> sorted(keys)
[(1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 2), (1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 4), (1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 5)]
>>> keys = sorted(keys)
>>> bisect.bisect(keys, three)
1
>>> keys[bisect.bisect(keys, three):]
[(1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 4), (1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 5)]
>>> six = (1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 6)
>>> keys[bisect.bisect(keys, six):]
[]
>>> keys[bisect.bisect_right(keys, six):]
[]
>>> keys[bisect.bisect_left(keys, six):]
[]
>>> bisect.bisect(keys, six)
3
>>> keys.append(six)
>>> keys[bisect.bisect_left(keys, six):]
[(1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 6)]
>>> keys[bisect.bisect(keys, six):]
[]
>>> keys[bisect.bisect(keys, six):]
[]
>>> keys[bisect.bisect(keys, three):]
[(1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 4), (1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 5), (1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9, 1, 6)]"""
