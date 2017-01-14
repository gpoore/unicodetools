# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the BSD 3-Clause License:
# http://opensource.org/licenses/BSD-3-Clause
#


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
import unicodetools.coding as coding
import pytest
import itertools



def test_chr_ord():
    # Check round trip
    for n in range(0x10FFFF+1):
        assert coding.ord_surrogate(coding.chr_surrogate(n)) == n
    # Check against hex values produced by a roundabout series of encoding
    # and decoding
    for n in itertools.chain(range(0xD800), range(0xDFFF+1, 0x10FFFF+1)):
        cp_str = '\\U{0:08x}'.format(n).encode('ascii').decode('unicode_escape')
        hex_utf16 = ''.join('{0:02x}'.format(ord(c)) for c in cp_str.encode('utf-16be').decode('latin1'))
        hex_chr = ''.join('{0:04x}'.format(ord(c)) for c in coding.chr_surrogate(n))
        assert hex_utf16 == hex_chr
    # Check against a single known value
    assert 0x1F600 == coding.ord_surrogate(chr(0xD83D) + chr(0xDE00))
    assert coding.chr_surrogate(0x1F600) == chr(0xD83D) + chr(0xDE00)
