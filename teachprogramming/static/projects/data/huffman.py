"""
https://en.wikipedia.org/wiki/Huffman_coding
https://en.wikipedia.org/wiki/Canonical_Huffman_code
https://www.geeksforgeeks.org/canonical-huffman-coding/
"""

import typing
from functools import reduce, total_ordering
from itertools import zip_longest, tee
from collections import defaultdict
from queue import PriorityQueue


def pairwise(iterable, fillvalue=None):
    """
    https://stackoverflow.com/a/5434936/3356840
    s -> (s0,s1), (s1,s2), (s2, s3), ...

    >>> tuple(pairwise((1,2,3)))
    ((1, 2), (2, 3), (3, None))
    """
    a, b = tee(iterable)
    next(b, None)
    return zip_longest(a, b, fillvalue=fillvalue)
def is_last(iterable):
    """
    >>> tuple(is_last('123'))
    (('1', False), ('2', False), ('3', True))
    """
    return ((a, True if b is None else False) for a, b in pairwise(iterable))



@total_ordering
class Tree():
    def __init__(self, left=None, right=None):
        self.left = left
        self.right = right

    def __cmp__(self, other):
        return False
    def __eq__(self, other):
        return self is other
    def __lt__(self, other):
        return False

    def depth_of_nodes(self):
        """
        >>> t = Tree(left='C', right=Tree(left=Tree(left='D', right='A'), right='B'))
        >>> tuple(t.depth_of_nodes())
        ((1, 'C'), (2, 'B'), (3, 'D'), (3, 'A'))
        """
        stack = [(1, self)]
        while stack:
            depth, i = stack.pop()
            if isinstance(i.left, self.__class__):
                stack.append((depth+1, i.left))
            else:
                yield (depth, i.left)
            if isinstance(i.right, self.__class__):
                stack.append((depth+1, i.right))
            else:
                yield (depth, i.right)

def _frequency_analysis(data: bytes) -> dict[str, int]:
    """
    >>> import random
    >>> fa = _frequency_analysis(b'ABCD' + b'A'*9 + b'C'*14 + b'D'*6)
    >>> {chr(k): v for k, v in fa.items()}
    {'A': 10, 'B': 1, 'C': 15, 'D': 7}
    """
    def _(acc, char):
        acc[char] += 1
        return acc
    return reduce(_, data, defaultdict(int))

class WeightTreeItem(typing.NamedTuple):
    weight: int
    item: typing.Union[int, Tree]
def _convert_to_PriorityQueue(fa) -> PriorityQueue:
    """
    >>> q = _convert_to_PriorityQueue({'A': 10, 'B': 1, 'C': 15, 'D': 7})
    >>> q.get()
    WeightTreeItem(weight=1, item='B')
    >>> q.get()
    WeightTreeItem(weight=7, item='D')
    >>> q.get()
    WeightTreeItem(weight=10, item='A')
    >>> q.get()
    WeightTreeItem(weight=15, item='C')
    """
    def _(q, item):
        key, weight = item
        q.put(WeightTreeItem(weight, key))
        return q
    return reduce(_, fa.items(), PriorityQueue())

def _build_tree_from_data(data):
    """
    # WeightTreeItem(weight=33, item=)
    >>> t = _build_tree_from_data(b'ABCD' + b'A'*9 + b'C'*14 + b'D'*6)
    >>> t
    <huffman.Tree object at 0x...>
    >>> chr(t.left)
    'C'
    >>> t.right
    <huffman.Tree object at 0x...>
    """
    q = _convert_to_PriorityQueue(_frequency_analysis(data))
    while q.qsize() > 1:
        a, b = q.get(), q.get()
        q.put(WeightTreeItem(a.weight + b.weight, Tree(a.item, b.item)))
    return q.get().item

def _normalise_tree_depths(tree) -> tuple[int]:
    """
    A dataset of every possible 0-255 byte is uniform. Each key length in the tree will be 8-bits
    >>> t = _build_tree_from_data(bytes(range(256)))
    >>> assert _normalise_tree_depths(t) == (8,)*256

    #>>> t = Tree(left=3, right=Tree(left=Tree(left=4, right=1), right=2))
    # +bytes(range(128)
    #>>> from itertools import groupby
    #>>> tuple((i, sum(1 for x in ll)) for i, ll in groupby(sorted(_normalise_tree_depths(t))))
    """
    i_depth = sorted((i, depth) for depth, i in sorted(tree.depth_of_nodes()))
    def pop_if_match(i):
        if i_depth:
            _i, _depth = i_depth[0]
            if i == _i:
                i_depth.pop(0)
                return _depth
        return 0
    return tuple(pop_if_match(i) for i in range(256))

def _build_tree_from_normalised_depths(normalised_depths) -> Tree:
    """
    #>>> t = _build_tree_from_normalised_depths((1, 2, 3))
    >>> t = _build_tree_from_normalised_depths((8,)*255)
    >>> t
    <huffman.Tree object at 0x...>
    >>> t.right
    'mpp'
    """
    # Take a list of 'bitlengths' in order for 0-255 and make a sorted bitdepth->character list
    assert len(normalised_depths) == 255
    normalised_character_to_huffman_binary_code = []
    previous_code = None
    for depth, character in sorted(zip(
        normalised_depths,
        range(256),
    )):
        if previous_code is None:
            previous_code = '0' * depth
            huffman_code = previous_code
        else:
            #huffman_code = "{0:b}".format(int(previous_code, base=2)+1)
            assert False, 'this needs to be some kind of shift bollox - finished this'
        if depth > len(previous_code):
            huffman_code += '0'*(depth-len(previous_code))
        normalised_character_to_huffman_binary_code.append((
            character,
            huffman_code,
        ))
        #breakpoint()
        previous_code = huffman_code
    # Build Tree
    root = Tree()
    for character, huffman_code in normalised_character_to_huffman_binary_code:
        t = root
        for binary_digit, _is_last in is_last(huffman_code):
            if binary_digit == '0':
                t.left = t.left or (character if _is_last else Tree())
                t = t.left
            if binary_digit == '1':
                t.right = t.right or (character if _is_last else Tree())
                t = t.right
    #breakpoint()
    return root


def encode(data: bytes) -> bytes:
    """
    >>> encode(b'AAAAACGTTATGCCTA')
    b''
    """
    return b''

def decode(data: bytes) -> bytes:
    """
    >>> decode(b'')
    b'AAAAACGTTATGCCTA'
    """
    return b''