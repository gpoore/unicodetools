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
from . import err
from . import coding
import itertools


# pylint: disable=E0602, W0622
if sys.version_info.major == 2:
    str = unicode
    chr = unichr
    itertools.zip_longest = itertools.izip_longest
    range = xrange
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

    The more Pythonic `.start` and `.end` are not used, because range regular
    expressions of the form `[\\Uxxxxxxxx-\\Uxxxxxxxx]` include both the
    first and last code points matched.

    The boolean keyword argument `unpaired_surrogates` determines whether
    unpaired surrogate code points (U+D800 - U+DFFF) are allowed; by default,
    they are not permitted.
    '''
    __slots__ = ['first', 'last', 'unpaired_surrogates']

    def __init__(self, first, last, unpaired_surrogates=False):
        if not all(isinstance(x, int) or isinstance(x, str) for x in (first, last)):
            raise TypeError('"first" and "last" must be integers or strings that represent single code points')
        if unpaired_surrogates not in (True, False):
            raise TypeError('"unpaired_surrogates" must be boolean')
        if isinstance(first, str):
            first = ord(first)
        if isinstance(last, str):
            last = ord(last)
        if not first <= last:
            raise ValueError('Must have "first" <= "last"')
        if (first <= 0xD800 <= last or first <= 0xDFFF <= last) and not unpaired_surrogates:
            raise ValueError('Individual Unicode surrogates (U+D800 - U+DFFF) are not allowed by default; use "unpaired_surrogates"=True if you must have them')
        if any(x < 0 or x > 0x10FFFF for x in (first, last)):
            raise ValueError('"first" and "last" must be in the range [0, 0x10FFFF]')
        self.first = first
        self.last = last
        self.unpaired_surrogates = unpaired_surrogates

    def __repr__(self):
        if not self.unpaired_surrogates:
            return '{0}.{1}(0x{2:04x}, 0x{3:04x})'.format(self.__module__, type(self).__name__, self.first, self.last)
        return '{0}.{1}(0x{2:04x}, 0x{3:04x}, unpaired_surrogates={4})'.format(self.__module__, type(self).__name__, self.first, self.last, self.unpaired_surrogates)


    def __iter__(self):
        for cp in range(self.first, self.last+1):
            yield cp

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


    _ascii_alphanums = set([cp for f, l in [('0', '9'), ('A', 'Z'), ('a', 'z')] for cp in range(ord(f), ord(l)+1)])

    @classmethod
    def generic_escape(cls, cp):
        '''
        Code point escape function for generic regular expression patterns.
        Return ASCII alphanumeric code points as literal characters, and use
        `\\uXXXX` and `\\UXXXXXXXX` escapes otherwise.
        '''
        if cp <= 0xFFFF:
            if cp in cls._ascii_alphanums:
                return chr(cp)
            else:
                return '\\u{0:04X}'.format(cp)
        return '\\U{0:08X}'.format(cp)


    def as_generic_re_pattern(self, *args, **kwargs):
        '''
        Express the range as a generic regular expression pattern.  With the
        default settings, this is suitable for compiling with the `re`
        module under Python 3.3+, but MUST NOT be used with any earlier
        version of Python, because the result may compile but WILL NOT work
        correctly since `\\u` and `\\U` escapes were not recognized prior to
        Python 3.3.

        If `surrogate_pairs=True`, Unicode surrogate pairs are used to
        represent code points above 0xFFFF.

        If `escape_func` is provided, it must be a function that takes a code
        point as an integer and returns an appropriately escaped string
        representation suitable for use either individually or as part of
        a regular expression range `[<first>-<last>]`.

        Reference for `re` escape support:
            https://docs.python.org/3.6/library/re.html
        '''
        if args:
            raise TypeError('Only explicit keyword arguments are accepted')
        surrogate_pairs = kwargs.pop('surrogate_pairs', False)
        escape_func = kwargs.pop('escape_func', None)
        if kwargs:
            raise TypeError('Invalid keyword argument(s):  {0}'.format(', '.join(str(k) for k in kwargs)))
        if surrogate_pairs not in (True, False):
            raise TypeError('"surrogate_pairs" must be boolean')
        if escape_func is None:
            escape_func = self.generic_escape
        elif not hasattr(escape_func, '__call__'):
            raise TypeError('"escape_func" must be callable')
        if self.first == self.last:
            if not surrogate_pairs:
                pattern = escape_func(self.first)
            else:
                pattern = ''.join(escape_func(ord(c)) for c in coding.chr_surrogate(self.first))
        elif not surrogate_pairs or self.last <= 0xFFFF:
            pattern = '[{0}-{1}]'.format(escape_func(self.first), escape_func(self.last))
        else:
            sub_patterns = []
            if self.first <= 0xFFFF:
                if self.first == 0xFFFF:
                    sub_patterns.append(escape_func(0xFFFF))
                else:
                    sub_patterns.append('[{0}-{1}]'.format(escape_func(self.first), escape_func(0xFFFF)))
                first_astral = 0xFFFF+1
                last_astral = self.last
            else:
                first_astral = self.first
                last_astral = self.last
            high = None
            high_first = None
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
                        sub_patterns.append('{0}{1}'.format(*[escape_func(x) for x in (high, low_first)]))
                    elif high_first is not None and low_first == 0xDC00 and low_last == 0xDFFF:
                        sub_patterns[-1] = '[{0}-{1}][{2}-{3}]'.format(*[escape_func(x) for x in (high_first, high, low_first, low_last)])
                    else:
                        sub_patterns.append('{0}[{1}-{2}]'.format(*[escape_func(x) for x in (high, low_first, low_last)]))
                else:
                    h_next, l_next = (ord(c) for c in coding.chr_surrogate(cp_next))
                    # Don't need `l_next != l + 1` check since working with
                    # contiguous range
                    if h_next != h:
                        low_last = l
                        if low_first == low_last:
                            sub_patterns.append('{0}{1}'.format(*[escape_func(x) for x in (high, low_first)]))
                            high_first = None
                        elif high_first is not None and low_first == 0xDC00 and low_last == 0xDFFF:
                            sub_patterns[-1] = '[{0}-{1}][{2}-{3}]'.format(*[escape_func(x) for x in (high_first, high, low_first, low_last)])
                        else:
                            sub_patterns.append('{0}[{1}-{2}]'.format(*[escape_func(x) for x in (high, low_first, low_last)]))
                            if low_first == 0xDC00 and low_last == 0xDFFF:
                                high_first = high
                            else:
                                high_first = None
                        high = None
            pattern = '|'.join(p for p in sub_patterns)
        return pattern


    def as_python_3_3_plus_re_pattern(self):
        '''
        Express the range as a regular expression pattern suitable for
        compiling with `re` under Python 3.3+.
        '''
        return self.as_generic_re_pattern()


    @classmethod
    def python_before_3_3_escape(cls, cp):
        '''
        Code point escape function for generic regular expression patterns.
        Return ASCII alphanumeric code points as literal characters, and use
        `\\<literal code point>` otherwise.
        '''
        if cp in cls._ascii_alphanums:
            return chr(cp)
        return '\\' + chr(cp)


    def as_python_before_3_3_re_pattern(self, *args, **kwargs):
        '''
        Express the range as a regular expression pattern suitable for
        compiling with `re` under Python < 3.3, with the specified build
        width.
        '''
        if args:
            raise TypeError('Only explicit keyword arguments are accepted')
        if 'surrogate_pairs' not in kwargs:
            raise TypeError('Keyword argument "surrogate_pairs" (build width) is required')
        surrogate_pairs = kwargs.pop('surrogate_pairs')
        if kwargs:
            raise TypeError('Invalid keyword argument(s):  {0}'.format(', '.join(str(k) for k in kwargs)))
        return self.as_generic_re_pattern(surrogate_pairs=surrogate_pairs, escape_func=self.python_before_3_3_escape)


    def as_current_python_version_re_pattern(self):
        '''
        Express the range as a regular expression pattern suitable for
        compiling under the current version of Python.  This accounts for
        whether `\\u` and `\\U` escapes are supported (Python 3.3+) as well
        as wide vs. narrow builds (Python < 3.3).
        '''
        if sys.version_info.major == 2 or (sys.version_info.major == 3 and sys.version_info.minor < 3):
            if sys.maxunicode == 0xFFFF:
                surrogate_pairs = True
            else:
                surrogate_pairs = False
            version_pattern = self.as_python_before_3_3_re_pattern(surrogate_pairs=surrogate_pairs)
        else:
            version_pattern = self.as_python_3_3_plus_re_pattern()
        return version_pattern




def codepoints_to_codepointranges(*containers, **kwargs):
    '''
    Convert containers of code points into a list of CodePointRange
    objects.
    '''
    codepoints = set()
    if len(containers) == 0:
        raise TypeError('One or more containers are required as arguments')
    unpaired_surrogates = kwargs.pop('unpaired_surrogates', False)
    if kwargs:
        raise TypeError('Unknown keyword argument(s):  {0}'.format(', '.join(str(k) for k in kwargs)))
    for container in containers:
        if all(isinstance(x, int) for x in container):
            for x in container:
                codepoints.update((x,))
        elif all(isinstance(x, str) for x in container):
            for x in container:
                # The current `ord()` will be appropriate for narrow vs. wide
                # builds or for Python 3.3+, so no additional checking is
                # needed; `ord()` will raise any necessary errors.
                x_int = ord(x)
                codepoints.update((x_int,))
        else:
            raise TypeError('Arguments must be containers consisting solely of integers or solely of Unicode strings that represent individual code points')
    if not codepoints:
        raise TypeError('Arguments must be non-empty containers')

    sorted_codepoints = sorted(codepoints)
    if sorted_codepoints[0] < 0 or sorted_codepoints[-1] > 0x10FFFF:
        raise ValueError('Valid code points are in the range [0, 0x10FFFF]')

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




class CodePointMultiRange(object):
    '''
    A collection of non-overlapping CodePointRanges.  Methods allow the
    creation of minimal regular expression patterns.

    A single keyword argument is required in initialization.  Keyword
    `codepoints` specifies a sequence of code points that will be converted
    to a list of CodePointRange instances.  Keyword `codepointranges`
    specifies a sequence of CodePointRange instances.
    '''
    def __init__(self, *args, **kwargs):
        if args:
            raise TypeError('Only explicit keyword arguments are accepted')
        codepoints = kwargs.pop('codepoints', None)
        codepointranges = kwargs.pop('codepointranges', None)
        if kwargs:
            raise TypeError('Invalid keyword argument(s):  {0}'.format(', '.join(str(k) for k in kwargs)))
        if (codepoints is None and codepointranges is None) or (codepoints is not None and codepointranges is not None):
            raise TypeError('A single keyword argument is required ("codepoints" or "codepointranges")')
        if codepoints is not None:
            ranges_no_overlap = codepoints_to_codepointranges(codepoints)
        else:
            ranges = []
            for x in codepointranges:
                if isinstance(x, CodePointRange):
                    ranges.append(x)
                elif all(isinstance(y, CodePointRange) for y in x):
                    for y in x:
                        ranges.append(y)
                else:
                    raise TypeError('Keyword argument "codepointranges" must give CodePointRanges or containers of them')
            if not ranges:
                raise TypeError('Keyword argument "codepointranges" must give CodePointRanges or containers of them')
            ranges = sorted(ranges, key=lambda x: x.first)
            ranges_no_overlap = []
            ranges_iter = iter(ranges)
            r = next(ranges_iter)
            r_next = next(ranges_iter, None)
            while r_next is not None:
                if r_next.first in r or r_next.first == r.last + 1:
                    first = min(r.first, r_next.first)
                    last = max(r.last, r_next.last)
                    unpaired_surrogates = r.unpaired_surrogates or r_next.unpaired_surrogates
                    r = CodePointRange(first, last, unpaired_surrogates=unpaired_surrogates)
                    r_next = next(ranges_iter, None)
                else:
                    ranges_no_overlap.append(r)
                    r = r_next
                    r_next = next(ranges_iter, None)
            ranges_no_overlap.append(r)
        self.codepointranges = ranges_no_overlap

    def __repr__(self):
        return '{0}.{1}({2})'.format(self.__module__, type(self).__name__, ', '.join(repr(x) for x in self.codepointranges))

    def __iter__(self):
        for cp in itertools.chain(*self.codepointranges):
            yield cp

    def __eq__(self, other):
        if isinstance(other, type(self)) and self.codepointranges == other.codepointranges:
            return True
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __contains__(self, value):
        if not isinstance(value, int):
            return False
        return any(value in r for r in self.codepointranges)


    def _combine_re_patterns(self, re_patterns, surrogate_pairs):
        if not surrogate_pairs or self.codepointranges[-1].last <= 0xFFFF:
            final_patterns = []
            for p, r in zip(re_patterns, self.codepointranges):
                if r.first == r.last:
                    final_patterns.append(p)
                else:
                    # `[<first>-<last>]` -> `<first>-<last>`
                    final_patterns.append(p[1:-1])
            final_pattern = '[{0}]'.format(''.join(final_patterns))
        elif self.codepointranges[0].first > 0xFFFF:
            final_pattern = '|'.join(re_patterns)
        else:
            bmp_final_patterns = []
            astral_final_patterns = []
            for p, r in zip(re_patterns, self.codepointranges):
                if r.first == r.last:
                    if r.first <= 0xFFFF:
                        bmp_final_patterns.append(p)
                    else:
                        astral_final_patterns.append(p)
                else:
                    if r.last <= 0xFFFF:
                        bmp_final_patterns.append(p[1:-1])
                    elif r.first > 0xFFFF:
                        astral_final_patterns.append(p)
                    else:
                        p_bmp, p_astral = p.split('|', 1)
                        if r.first == 0xFFFF:
                            bmp_final_patterns.append(p_bmp)
                        else:
                            bmp_final_patterns.append(p_bmp[1:-1])
                        astral_final_patterns.append(p_astral)
            final_pattern = '[{0}]|{1}'.format(''.join(bmp_final_patterns), '|'.join(astral_final_patterns))
        return final_pattern


    def as_generic_re_pattern(self, *args, **kwargs):
        '''
        Express the range as a generic regular expression pattern.
        '''
        if args:
            raise TypeError('Only explicit keyword arguments are accepted')
        surrogate_pairs = kwargs.pop('surrogate_pairs', False)
        escape_func = kwargs.pop('escape_func', None)
        if kwargs:
            raise TypeError('Invalid keyword argument(s):  {0}'.format(', '.join(str(k) for k in kwargs)))
        re_patterns = [r.as_generic_re_pattern(surrogate_pairs=surrogate_pairs, escape_func=escape_func) for r in self.codepointranges]
        return self._combine_re_patterns(re_patterns, surrogate_pairs)


    def as_python_3_3_plus_re_pattern(self):
        '''
        Express the range as a regular expression pattern suitable for
        compiling with `re` under Python 3.3+.
        '''
        surrogate_pairs = False
        re_patterns = [r.as_python_3_3_plus_re_pattern() for r in self.codepointranges]
        return self._combine_re_patterns(re_patterns, surrogate_pairs)


    def as_python_before_3_3_re_pattern(self, *args, **kwargs):
        '''
        Express the range as a regular expression pattern suitable for
        compiling with `re` under Python < 3.3, with the specified build
        width.
        '''
        if args:
            raise TypeError('Only explicit keyword arguments are accepted')
        if 'surrogate_pairs' not in kwargs:
            raise TypeError('Keyword argument "surrogate_pairs" (build width) is required')
        surrogate_pairs = kwargs.pop('surrogate_pairs')
        if kwargs:
            raise TypeError('Invalid keyword argument(s):  {0}'.format(', '.join(str(k) for k in kwargs)))
        re_patterns = [r.as_python_before_3_3_re_pattern(surrogate_pairs=surrogate_pairs) for r in self.codepointranges]
        return self._combine_re_patterns(re_patterns, surrogate_pairs)


    def as_current_python_version_re_pattern(self):
        '''
        Express the range as a regular expression pattern suitable for
        compiling under the current version of Python.  This accounts for
        whether `\\u` and `\\U` escapes are supported (Python 3.3+) as well
        as wide vs. narrow builds (Python < 3.3).
        '''
        if sys.version_info.major == 2 or (sys.version_info.major == 3 and sys.version_info.minor < 3):
            if sys.maxunicode == 0xFFFF:
                surrogate_pairs = True
            else:
                surrogate_pairs = False
            version_combined_pattern = self.as_python_before_3_3_re_pattern(surrogate_pairs=surrogate_pairs)
        else:
            version_combined_pattern = self.as_python_3_3_plus_re_pattern()
        return version_combined_pattern
