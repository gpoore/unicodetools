# -*- coding: utf-8 -*-
#
# Copyright (c) 2016-2017, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the BSD 3-Clause License:
# http://opensource.org/licenses/BSD-3-Clause
#

'''
Utilities for working with collections of code points, in which the code
points are represented as integers.
'''


# pylint: disable=C0103, C0301


from __future__ import (division, print_function, absolute_import,
                        unicode_literals)


import sys
import os
from . import err
from . import coding
import itertools


# pylint: disable=E0602, W0622
if sys.version_info.major == 2:
    str = unicode
    chr = unichr
    itertools.zip_longest = itertools.izip_longest
# pylint: enable=E0602, W0622
# pylint: disable=W0622
if sys.maxunicode == 0xFFFF:
    chr = coding.chr_surrogate
    ord = coding.ord_surrogate
# pylint: enable=W0622




class CodePointRange(object):
    '''
    A range of code points from `.first` up to and including `.last`.

    `.first` and `.last` are integers, and iterating over the object also
    yields integers.  This avoids complications on narrow Python builds.

    The more Pythonic `.start`, `.end` are not used, because range regular
    expressions of the form `[\\Uxxxxxxxx-\\Uxxxxxxxx]` include both the
    first and last code points matched.
    '''
    __slots__ = ['first', 'last', 'unpaired_surrogates']

    def __init__(self, first, last, unpaired_surrogates=False):
        if not all(isinstance(x, int) or isinstance(x, str) for x in (first, last)):
            raise err.InitError('"first" and "last" must be integers or strings that represent single code points')
        if unpaired_surrogates not in (True, False):
            raise err.InitError('"unpaired_surrogates" must be boolean')
        if isinstance(first, str):
            first = ord(first)
        if isinstance(last, str):
            last = ord(last)
        if not first <= last:
            raise err.InitError('Must have "first" <= "last"')
        if (any(0xD800 <= x <= 0xDFFF for x in (first, last)) or (first < 0xD800 and last > 0xDFFF)) and not unpaired_surrogates:
            raise err.InitError('Individual Unicode surrogates (U+D800 - U+DFFF) are not allowed by default; use "unpaired_surrogates"=True if you must have them')
        if any(x < 0 or x > 0x10FFFF for x in (first, last)):
            raise err.InitError('"first" and "last" must be in the range [0, 0x10FFFF]')
        self.first = first
        self.last = last
        self.unpaired_surrogates = unpaired_surrogates

    def __repr__(self):
        return '{0}.{1}(0x{2:04X}, 0x{3:04X}, unpaired_surrogates={4})'.format(self.__module__, type(self).__name__, self.first, self.last, self.unpaired_surrogates)

    def __iter__(self):
        current = self.first
        last = self.last
        while current <= last:
            yield current
            current += 1

    def __eq__(self, other):
        if isinstance(other, type(self)) and self.first == other.first and self.last == other.last:
            return True
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __contains__(self, value):
        if not isinstance(value, int):
            return False
        return self.first <= value <= self.last


    def as_generic_re_pattern(self, utf16=False, escapefunc=None):
        '''
        Express the range as a generic regular expression pattern.  With the
        default settings, this is suitable for compiling with the `re`
        module under Python 3.3+, but MUST NOT be used with any earlier
        version of Python, because the result may compile but WILL NOT work
        correctly since `\\u` and `\\U` escapes were not recognized prior to
        Python 3.3.

        If `utf16=True`, Unicode surrogate pairs are used to represent code
        points above 0xFFFF.

        If `escapefunc` is provided, it must be a function that takes a code
        point as an integer and returns an appropriately escaped string
        representation suitable for use either individually or as part of
        a regular expression range `[<first>-<last>]`.

        Reference for `re` escape support:
            https://docs.python.org/3.6/library/re.html
        '''
        if utf16 not in (True, False):
            raise TypeError('"utf16" must be boolean')
        if escapefunc is None:
            def ef(cp):
                if cp <= 0xFFFF:
                    return '\\u{0:04X}'.format(cp)
                return '\\U{0:08X}'.format(cp)
            escapefunc = ef
        elif not hasattr(escapefunc, '__call__'):
            raise TypeError('"escapefunc" must be callable')
        if self.first == self.last:
            if not utf16:
                pattern = escapefunc(self.first)
            else:
                pattern = ''.join(escapefunc(ord(c)) for c in coding.chr_surrogate(self.first))
        elif not utf16 or self.last <= 0xFFFF:
            pattern = '[{0}-{1}]'.format(escapefunc(self.first), escapefunc(self.last))
        else:
            sub_patterns = []
            if self.first <= 0xFFFF:
                sub_patterns.append('[{0}-{1}]'.format(escapefunc(self.first), escapefunc(0xFFFF)))
                first_astral = 0xFFFF+1
                last_astral = self.last
            else:
                first_astral = self.first
                last_astral = self.last
            high = None
            current_iter = iter(range(first_astral, last_astral+1))
            next_iter = iter(range(first_astral, last_astral+1))
            next(next_iter)
            for cp, cp_next in itertools.zip_longest(current_iter, next_iter):
                h, l = (ord(c) for c in coding.chr_surrogate(cp))
                if high is None:
                    high = h
                    low_first = l
                if cp_next is None:
                    low_last = l
                    if low_first == low_last:
                        sub_patterns.append('{0}{1}'.format(escapefunc(high), escapefunc(low_first)))
                    else:
                        sub_patterns.append('{0}[{1}-{2}]'.format(escapefunc(high), escapefunc(low_first), escapefunc(low_last)))
                else:
                    h_next, l_next = (ord(c) for c in coding.chr_surrogate(cp_next))
                    # Don't need `l_next != l + 1` check since working with
                    # contiguous range
                    if h_next != h:
                        low_last = l
                        if low_first == low_last:
                            sub_patterns.append('{0}{1}'.format(escapefunc(high), escapefunc(low_first)))
                        else:
                            sub_patterns.append('{0}[{1}-{2}]'.format(escapefunc(high), escapefunc(low_first), escapefunc(low_last)))
                        high = None
            pattern = '|'.join(p for p in sub_patterns)
        return pattern


    def as_python_3_3_plus_re_pattern(self):
        '''
        Express the range as a regular expression pattern suitable for
        compiling with `re` with Python 3.3+.
        '''
        return self.as_generic_re_pattern()


    def as_python_before_3_3_re_pattern(self, **kwargs):
        '''
        Express the range as a regular expression pattern suitable for
        compiling with `re` with Python < 3.3, with the specified build width.
        '''
        if 'utf16' not in kwargs:
            raise TypeError('Keyword argument "utf16" (build width) is required')
        utf16 = kwargs.pop('utf16')
        if kwargs:
            raise TypeError('Invalid keyword argument(s):  {0}'.format(' '.join(str(k) for k in kwargs)))
        def ef(cp):
            if any(ord(first) <= cp <= ord(last) for first, last in [('0', '9'), ('A', 'Z'), ('a', 'z')]):
                return chr(cp)
            return '\\' + chr(cp)
        return self.as_generic_re_pattern(utf16=utf16, escapefunc=ef)


    def as_current_python_version_re_pattern(self):
        '''
        Express the range as a regular expression pattern suitable for
        compiling with the current version of Python.  This accounts for
        whether `\\u` and `\\U` escapes are supported (Python 3.3+) as well
        as wide vs. narrow builds (Python < 3.3).
        '''
        if sys.version_info.major == 2 or (sys.version_info.major == 3 and sys.version_info.minor < 3):
            if sys.maxunicode == 0xFFFF:
                utf16 = True
            else:
                utf16 = False
            version_pattern = self.as_python_before_3_3_re_pattern(utf16=utf16)
        else:
            version_pattern = self.as_python_3_3_plus_re_pattern()
        return version_pattern




def containers_to_codepointranges(*containers, **kwargs):
    '''
    Convert containers of code points into a sequence of CodePointRange
    objects.
    '''
    codepoints = set()
    if len(containers) == 0:
        raise err.InitError('One or more containers (tuples, lists, sets) are required as arguments')
    unpaired_surrogates = kwargs.pop('unpaired_surrogates', False)
    if unpaired_surrogates not in (True, False):
        raise err.InitError('"unpaired_surrogates" must be boolean')
    if kwargs:
        raise err.InitError('Unknown keyword argument(s):  {0}'.format(', '.join(k for k in kwargs)))
    for container in containers:
        if not any(isinstance(container, t) for t in (tuple, list, set)):
            raise err.InitError('Arguments must be instances of tuple, list, or set')
        if all(isinstance(x, int) for x in container):
            for x in container:
                codepoints.update((x,))
        elif all(isinstance(x, str) for x in container):
            for x in container:
                # The current `ord()` will be appropriate for narrow vs. wide
                # builds or for Python 3.3+, so no additional checking is
                # needed; `ord()` will raise any necessary errors.
                x_int = ord(x)
                if not unpaired_surrogates and 0xD800 <= x_int <= 0xDFFF:
                    raise err.InitError('Individual Unicode surrogates (U+D800 - U+DFFF) are not allowed by default; use "unpaired_surrogates"=True if you must have them')
                codepoints.update((x_int,))
        else:
            raise err.InitError('Arguments must be containers consisting solely of integers or solely of Unicode strings that represent individual code points')
    if not codepoints:
        raise err.InitError('Arguments must be non-empty containers')

    sorted_codepoints = sorted(codepoints)
    if sorted_codepoints[0] < 0 or sorted_codepoints[-1] > 0x10FFFF:
        raise err.InitError('Valid code points are in the range [0, 0x10FFFF]')

    codepoint_ranges = []
    first = None
    current_iter = iter(sorted_codepoints)
    next_iter = iter(sorted_codepoints)
    next(next_iter)
    for cp, cp_next in itertools.zip_longest(current_iter, next_iter):
        if first is None:
            first = cp
        if cp_next is None or cp_next != cp + 1:
            last = cp
            codepoint_ranges.append(CodePointRange(first, last, unpaired_surrogates=unpaired_surrogates))
            first = None
    return codepoint_ranges
