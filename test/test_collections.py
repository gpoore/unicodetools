# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the BSD 3-Clause License:
# http://opensource.org/licenses/BSD-3-Clause
#


# pylint: disable=C0301

from __future__ import (division, print_function, absolute_import,
                        unicode_literals)


import sys
import os


# pylint: disable=E0602, W0622
if sys.version_info.major == 2:
    str = unicode
    chr = unichr
# pylint: enable=E0602, W0622


if all(os.path.isdir(x) for x in ('unicodetools', 'test', 'doc')):
    sys.path.insert(0, '.')


import unicodetools as mdl
import unicodetools.err as err
import unicodetools.coding as coding
# pylint: disable=W0622
if sys.maxunicode == 0xFFFF:
    chr = coding.chr_surrogate
    ord = coding.ord_surrogate
# pylint: enable=W0622
import pytest
import random
import re



def test_CodePointRange():
    cpr = mdl.CodePointRange('\u0000', '\u000F')
    assert cpr.first == 0x0
    assert cpr.last == 0xF
    assert not cpr.unpaired_surrogates

    cpr = mdl.CodePointRange('\u0000', '\U0010FFFF', unpaired_surrogates=True)
    assert sum(1 for x in cpr) == 0x10FFFF+1

    cpr = mdl.CodePointRange(0xD800, 0xDFFF, unpaired_surrogates=True)
    assert cpr.first == 0xD800
    assert cpr.last == 0xDFFF
    assert cpr.unpaired_surrogates
    assert len(list(cpr)) == 0xDFFF - 0xD800 + 1

    assert list(mdl.CodePointRange(0, 10)) == list(range(0, 11))
    assert len(list(mdl.CodePointRange('\u0000', '\u000F'))) == 16

    for first, last in [(-1, 10), (11, 10), (0, 0x10FFFF+1),
                        (0xD800, 0x10FFFF), ('\uD800', '\U0010FFFF'),
                        (0, 0xDFFF), ('\u0000', '\uDFFF')]:
        with pytest.raises(ValueError):
            mdl.CodePointRange(first, last)

    assert mdl.CodePointRange(0, 10) == mdl.CodePointRange(0, 10)
    assert mdl.CodePointRange(0, 10) != mdl.CodePointRange(0, 11)

    assert mdl.CodePointRange(0xAF, 0xA10).as_generic_re_pattern() == '[\\u00AF-\\u0A10]'
    assert mdl.CodePointRange(0xAF, 0xA10).as_generic_re_pattern(as_escaped_source=True) == '[\\\\u00AF-\\\\u0A10]'
    assert mdl.CodePointRange(0xAF, 0xA10).as_python_3_3_plus_re_pattern(as_escaped_source=True) == '[\\\\u00AF-\\\\u0A10]'
    assert mdl.CodePointRange(0xAF, 0xA10).as_python_before_3_3_re_pattern(surrogate_pairs=False, as_escaped_source=True) == '[\\\\\\u00AF-\\\\\\u0A10]'
    assert mdl.CodePointRange(0x100AF, 0xF0A10).as_generic_re_pattern() == '[\\U000100AF-\\U000F0A10]'
    assert mdl.CodePointRange(0x100AF, 0xF0A10).as_generic_re_pattern(as_escaped_source=True) == '[\\\\U000100AF-\\\\U000F0A10]'
    assert mdl.CodePointRange(0x100AF, 0xF0A10).as_python_before_3_3_re_pattern(surrogate_pairs=False, as_escaped_source=True) == '[\\\\\\U000100AF-\\\\\\U000F0A10]'

    for pair in [(0x0, 0x0), (0x100, 0xFFF), (0x30, 0xFF),
                 (0xFFFF-1, 0xFFFF), (0xFFFF-1, 0xFFFF+1), (0xFFFF, 0xFFFF+1),
                 (0xFFF0, 0x1000FF), (0x101111, 0x10FFFF)]:
        r = mdl.CodePointRange(pair[0], pair[1])
        if sys.maxunicode > 0xFFFF:
            p = re.compile(r.as_current_python_version_re_pattern())
            for cp in range(0, 0x10FFFF+1):
                if cp in r:
                    assert p.match(chr(cp))
                else:
                    assert p.match(chr(cp)) is None
        p = re.compile(r.as_python_before_3_3_re_pattern(surrogate_pairs=True))
        for cp in range(0, 0x10FFFF+1):
            if cp in r:
                assert p.match(coding.chr_surrogate(cp))
            else:
                assert p.match(coding.chr_surrogate(cp)) is None

    for cs, pat in [(('\uD800\uDFFF', '\uD801\uDC00'), '\\uD800\\uDFFF|\\uD801\\uDC00'),
                    (('\uD800\uDFFE', '\uD801\uDC00'), '\\uD800[\\uDFFE-\\uDFFF]|\\uD801\\uDC00'),
                    (('\uD800\uDFFF', '\uD801\uDC01'), '\\uD800\\uDFFF|\\uD801[\\uDC00-\\uDC01]'),
                    (('\uD800\uDFFF', '\uD802\uDC00'), '\\uD800\\uDFFF|\\uD801[\\uDC00-\\uDFFF]|\\uD802\\uDC00'),
                    (('\uD800\uDFFF', '\uD802\uDC02'), '\\uD800\\uDFFF|\\uD801[\\uDC00-\\uDFFF]|\\uD802[\\uDC00-\\uDC02]'),
                    (('\uD800\uDFFF', '\uD805\uDFFF'), '\\uD800\\uDFFF|[\\uD801-\\uD805][\\uDC00-\\uDFFF]'),
                    (('\uD800\uDFFF', '\uD806\uDC00'), '\\uD800\\uDFFF|[\\uD801-\\uD805][\\uDC00-\\uDFFF]|\\uD806\\uDC00')]:
        assert mdl.CodePointRange(coding.ord_surrogate(cs[0]), coding.ord_surrogate(cs[1])).as_generic_re_pattern(surrogate_pairs=True) == pat
    for cs, pat in [(('\uD800\uDFFF', '\uD801\uDC00'), '\\\\uD800\\\\uDFFF|\\\\uD801\\\\uDC00'),
                    (('\uD800\uDFFE', '\uD801\uDC00'), '\\\\uD800[\\\\uDFFE-\\\\uDFFF]|\\\\uD801\\\\uDC00'),
                    (('\uD800\uDFFF', '\uD801\uDC01'), '\\\\uD800\\\\uDFFF|\\\\uD801[\\\\uDC00-\\\\uDC01]'),
                    (('\uD800\uDFFF', '\uD802\uDC00'), '\\\\uD800\\\\uDFFF|\\\\uD801[\\\\uDC00-\\\\uDFFF]|\\\\uD802\\\\uDC00'),
                    (('\uD800\uDFFF', '\uD802\uDC02'), '\\\\uD800\\\\uDFFF|\\\\uD801[\\\\uDC00-\\\\uDFFF]|\\\\uD802[\\\\uDC00-\\\\uDC02]'),
                    (('\uD800\uDFFF', '\uD805\uDFFF'), '\\\\uD800\\\\uDFFF|[\\\\uD801-\\\\uD805][\\\\uDC00-\\\\uDFFF]'),
                    (('\uD800\uDFFF', '\uD806\uDC00'), '\\\\uD800\\\\uDFFF|[\\\\uD801-\\\\uD805][\\\\uDC00-\\\\uDFFF]|\\\\uD806\\\\uDC00')]:
        assert mdl.CodePointRange(coding.ord_surrogate(cs[0]), coding.ord_surrogate(cs[1])).as_generic_re_pattern(surrogate_pairs=True, as_escaped_source=True) == pat




def test_codepoints_to_codepointranges():
    assert mdl.codepoints_to_codepointranges([0]) == [mdl.CodePointRange(0, 0)]

    cps1 = list(range(0, 10))
    random.shuffle(cps1)
    ans1 = [mdl.CodePointRange(min(cps1), max(cps1))]
    assert mdl.codepoints_to_codepointranges(cps1) == ans1
    assert mdl.codepoints_to_codepointranges([chr(x) for x in cps1]) == ans1
    cps2 = list(range(20, 40))
    random.shuffle(cps2)
    ans12 = [mdl.CodePointRange(min(cps1), max(cps1)), mdl.CodePointRange(min(cps2), max(cps2))]
    assert mdl.codepoints_to_codepointranges(cps1, cps2) == ans12
    assert mdl.codepoints_to_codepointranges(cps2, cps1) == ans12
    assert mdl.codepoints_to_codepointranges([chr(x) for x in cps1], [chr(x) for x in cps2]) == ans12
    assert mdl.codepoints_to_codepointranges([chr(x) for x in cps2], [chr(x) for x in cps1]) == ans12

    for cp_first, cp_last in [(-1, 1), (0x10FFFF, 0x10FFFF+1), (0, 0xD800), (0xDFFF, 0x10FFFF)]:
        with pytest.raises(ValueError):
            mdl.codepoints_to_codepointranges([cp_first, cp_last])
    for cp_first, cp_last in [(0, 0xD800), (0xDFFF, 0x10FFFF)]:
        ans = [mdl.CodePointRange(cp_first, cp_last, unpaired_surrogates=True)]
        assert mdl.codepoints_to_codepointranges(list(range(cp_first, cp_last+1)), unpaired_surrogates=True) == ans




def test_CodePointMultiRange():
    alphanum = [cp for f, l in [('0', '9'), ('A', 'Z'), ('a', 'z')] for cp in range(ord(f), ord(l)+1)]
    for n in range(100):
        random.shuffle(alphanum)
    assert mdl.CodePointMultiRange(codepoints=alphanum).as_generic_re_pattern() == '[0-9A-Za-z]'
    assert mdl.CodePointMultiRange(codepoints=alphanum).as_python_3_3_plus_re_pattern() == '[0-9A-Za-z]'
    assert mdl.CodePointMultiRange(codepoints=alphanum).as_python_before_3_3_re_pattern(surrogate_pairs=False) == '[0-9A-Za-z]'
    assert mdl.CodePointMultiRange(codepoints=alphanum).as_python_before_3_3_re_pattern(surrogate_pairs=True) == '[0-9A-Za-z]'
    assert mdl.CodePointMultiRange(codepoints=alphanum).as_current_python_version_re_pattern() == '[0-9A-Za-z]'

    with pytest.raises(TypeError):
        mdl.CodePointMultiRange(alphanum)


    for n in range(100):
        random.shuffle(alphanum)
    rs = [mdl.codepoints_to_codepointranges(x) for x in [alphanum[:10], alphanum[10:20], alphanum[20:-1], [alphanum[-1]]]]
    assert mdl.CodePointMultiRange(codepointranges=rs).as_generic_re_pattern() == '[0-9A-Za-z]'


    for n in range(100):
        random.shuffle(alphanum)
    rs = [mdl.codepoints_to_codepointranges(x) for x in [alphanum[:20], alphanum[10:30], alphanum[20:]]]
    assert mdl.CodePointMultiRange(codepointranges=rs).codepointranges == [mdl.CodePointRange('0', '9'), mdl.CodePointRange('A', 'Z'), mdl.CodePointRange('a', 'z')]


    for cps, pat in [([0x0, 0xFFFF, 0x10000], '[\\u0000\\uFFFF-\\U00010000]'),
                     ([0x0, 0xFFFE, 0x10000], '[\\u0000\\uFFFE\\U00010000]'),
                     ([0x0, 0x2, 0xFFFE, 0x10000], '[\\u0000\\u0002\\uFFFE\\U00010000]'),
                     ([0x0, 0x1, 0x2, 0xFFFE, 0xFFFF, 0x10000], '[\\u0000-\\u0002\\uFFFE-\\U00010000]'),
                     ([0x0, 0x1, 0x2, 0xFFFE, 0xFFFF, 0x10000, 0x10001], '[\\u0000-\\u0002\\uFFFE-\\U00010001]'),
                     ([0x0, 0x1, 0x2, 0xFFFE, 0xFFFF, 0x10000, 0x10001, 0x10002], '[\\u0000-\\u0002\\uFFFE-\\U00010002]'),
                     ([0x0, 0x1, 0x2, 0xFFFF, 0x10000, 0x10001, 0x10002], '[\\u0000-\\u0002\\uFFFF-\\U00010002]')]:
        assert mdl.CodePointMultiRange(codepoints=cps).as_generic_re_pattern() == pat

    for cps, pat in [([0x0, 0xFFFF, 0x10000], '[\\u0000\\uFFFF]|\\uD800\\uDC00'),
                     ([0x0, 0xFFFE, 0x10000], '[\\u0000\\uFFFE]|\\uD800\\uDC00'),
                     ([0x0, 0x2, 0xFFFE, 0x10000], '[\\u0000\\u0002\\uFFFE]|\\uD800\\uDC00'),
                     ([0x0, 0x1, 0x2, 0xFFFE, 0xFFFF, 0x10000], '[\\u0000-\\u0002\\uFFFE-\\uFFFF]|\\uD800\\uDC00'),
                     ([0x0, 0x1, 0x2, 0xFFFE, 0xFFFF, 0x10000, 0x10001], '[\\u0000-\\u0002\\uFFFE-\\uFFFF]|\\uD800[\\uDC00-\\uDC01]'),
                     ([0x0, 0x1, 0x2, 0xFFFE, 0xFFFF, 0x10000, 0x10001, 0x10002], '[\\u0000-\\u0002\\uFFFE-\\uFFFF]|\\uD800[\\uDC00-\\uDC02]'),
                     ([0x0, 0x1, 0x2, 0xFFFF, 0x10000, 0x10001, 0x10002], '[\\u0000-\\u0002\\uFFFF]|\\uD800[\\uDC00-\\uDC02]')]:
        assert mdl.CodePointMultiRange(codepoints=cps).as_generic_re_pattern(surrogate_pairs=True) == pat





