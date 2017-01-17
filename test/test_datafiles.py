# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the BSD 3-Clause License:
# http://opensource.org/licenses/BSD-3-Clause
#


# pylint:  disable=C0103, C0301
from __future__ import (division, print_function, absolute_import,
                        unicode_literals)


import sys
import os
if all(os.path.isdir(x) for x in ('unicodetools', 'test', 'doc')):
    sys.path.insert(0, '.')


import unicodetools as mdl
import unicodetools.coding as coding
import unicodetools.err as err
import pytest
import unicodedata
if unicodedata.unidata_version != mdl.UNICODE_VERSION:
    try:
        import unicodedata2 as unicodedata
        if unicodedata.unidata_version != mdl.UNICODE_VERSION:
            unicodedata = None
    except ImportError:
        unicodedata = None
try:
    import regex
except ImportError:
    regex = None


# pylint: disable=E0602, W0622
if sys.version_info.major == 2:
    str = unicode
    chr = unichr
# pylint: enable=E0602, W0622
# pylint: disable=W0622
if sys.maxunicode == 0xFFFF:
    chr = coding.chr_surrogate
    ord = coding.ord_surrogate
# pylint: enable=W0622




def test_against_unicodedata():
    '''
    Check against `unicodedata` or `unicodedata2` if available with the
    correct version of Unicode.
    '''
    if unicodedata is None:
        raise Exception('Packages unicodedata and unicodedata2 are not available with the necessary version of Unicode ({0}); many consistency tests were omitted'.format(mdl.UNICODE_VERSION))
    ucdf = mdl.UCDFiles()

    ud = ucdf.unicodedata
    for cp in range(0, 0x10FFFF+1):
        c = chr(cp)
        if cp in ud:
            name = unicodedata.name(c, None)
            if name is None:
                # Handle missing names in unicodedata
                # Compare Table 4-13 in Unicode Standard
                # http://www.unicode.org/versions/Unicode9.0.0/ch04.pdf
                if 0x17000 <= cp <= 0x187EC:
                    assert ud[cp]['Name'] == 'TANGUT IDEOGRAPH-{0:04X}'.format(cp)
                else:
                    assert ud[cp]['Name'] == ''
            else:
                assert name == ud[cp]['Name']
            decimal, digit, numeric = (unicodedata.decimal(c, None), unicodedata.digit(c, None), unicodedata.numeric(c, None))
            if any(x is not None for x in (decimal, digit, numeric)):
                if decimal is not None:
                    assert decimal == int(ud[cp]['Numeric_Value']) and ud[cp]['Numeric_Type'] == 'Decimal' and digit is not None and decimal is not None
                elif digit is not None:
                    assert digit == int(ud[cp]['Numeric_Value']) and ud[cp]['Numeric_Type'] == 'Digit' and decimal is None and numeric is not None
                elif numeric is not None:
                    try:
                        num = float(ud[cp]['Numeric_Value'])
                    except ValueError:
                        if '/' in ud[cp]['Numeric_Value']:
                            numerator, denominator = ud[cp]['Numeric_Value'].split('/')
                            num = float(numerator)/float(denominator)
                        else:
                            raise
                    assert numeric == num and ud[cp]['Numeric_Type'] == 'Numeric' and digit is None and decimal is None
                else:
                    raise Exception
            else:
                assert ud[cp]['Numeric_Value'] == 'NaN' and ud[cp]['Numeric_Type'] == 'None'
            assert unicodedata.category(c) == ud[cp]['General_Category']
            assert unicodedata.bidirectional(c) == ud[cp]['Bidi_Class']
            assert unicodedata.combining(c) == int(ud[cp]['Canonical_Combining_Class'])
            assert unicodedata.mirrored(c) == ud[cp]['Bidi_Mirrored']
            if unicodedata.decomposition(c) == '':
                if ud[cp]['Name'].startswith('HANGUL SYLLABLE'):
                    # The Hangul syllables lack decomposition mapping in
                    # unicodedata, so calculate with a full decomposition
                    # followed by a partial composition (Unicode Standard,
                    # chapter 3.12)
                    decomp = unicodedata.normalize('NFD', c)
                    if len(decomp) == 3:
                        decomp = unicodedata.normalize('NFC', decomp[:2]) + decomp[-1]
                    decomp = tuple(ord(x) for x in decomp)
                    assert decomp == ud[cp]['Decomposition_Mapping']
                else:
                    assert ud[cp]['Decomposition_Mapping'] == (cp,)
            else:
                x = unicodedata.decomposition(c)
                if '<' in x:
                    x = x.split('>', 1)[1].strip()
                x = tuple(int(y, 16) for y in x.split('\x20'))
                assert x == ud[cp]['Decomposition_Mapping']

    dbc = ucdf.derivedbidiclass
    for cp in range(0, 0x10FFFF+1):
        c = chr(cp)
        # Only compare assigned code points, because unicodedata and
        # unicodedata2 lack correct defaults for unassigned
        if cp in dbc and cp in ud:
            assert unicodedata.bidirectional(c) == dbc[cp]['Bidi_Class']

    eaw = ucdf.eastasianwidth
    deaw = ucdf.derivedeastasianwidth
    for cp in range(0, 0x10FFFF+1):
        c = chr(cp)
        # Only compare assigned code points, because unicodedata and
        # unicodedata2 lack correct defaults for unassigned
        if cp in eaw and cp in ud:
            assert unicodedata.east_asian_width(c) == eaw[cp]['East_Asian_Width']
        if cp in deaw and cp in ud:
            assert unicodedata.east_asian_width(c) == deaw[cp]['East_Asian_Width']




def test_against_regex():
    '''
    Test against the regex package if available.

    On a narrow Python build, this can only test code points <= 0xFFFF.  So
    it is important to test on Python 3.3+, or on a wide build, to get
    complete coverage.
    '''
    if regex is None:
        raise Exception('The regex package was not available; many consistency tests were omitted.')
    ucdf = mdl.UCDFiles()
    ud = ucdf.unicodedata

    # Note that tuples are passed to `set.update()` in the tests.  This
    # keeps strings intact; otherwise they will be iterated code point by
    # code point, with each individual code point being added to the sets.

    bl = ucdf.blocks
    blocks = set()
    for cp, cpd in bl.items():
        blocks.update((cpd['Block'],))
    for block in blocks:
        if sys.maxunicode == 0xFFFF:
            assert all(regex.match(r'\p{{block={0}}}$'.format(block), s) for s in (chr(cp) for cp, cpd in bl.items() if block == cpd['Block'] and cp <= 0xFFFF))
        else:
            assert all(regex.match(r'\p{{block={0}}}$'.format(block), s) for s in (chr(cp) for cp, cpd in bl.items() if block == cpd['Block']))

    dcp = ucdf.derivedcoreproperties
    props = set()
    for cp, cpd in dcp.items():
        for prop in cpd:
            props.update((prop,))
    for prop in props:
        if sys.maxunicode == 0xFFFF:
            assert all(regex.match(r'\p{{{0}}}$'.format(prop), s) for s in (chr(cp) for cp, cpd in dcp.items() if prop in cpd and cp <= 0xFFFF))
        else:
            assert all(regex.match(r'\p{{{0}}}$'.format(prop), s) for s in (chr(cp) for cp, cpd in dcp.items() if prop in cpd))

    pl = ucdf.proplist
    props = set()
    for cp, cpd in pl.items():
        for prop in cpd:
            props.update((prop,))
    for prop in props:
        if sys.maxunicode == 0xFFFF:
            assert all(regex.match(r'\p{{{0}}}$'.format(prop), s) for s in (chr(cp) for cp, cpd in pl.items() if prop in cpd and cp <= 0xFFFF))
        else:
            assert all(regex.match(r'\p{{{0}}}$'.format(prop), s) for s in (chr(cp) for cp, cpd in pl.items() if prop in cpd))

    sc = ucdf.scripts
    scripts = set()
    for cp, cpd in sc.items():
        scripts.update((cpd['Script'],))
    for script in scripts:
        if sys.maxunicode == 0xFFFF:
            assert all(regex.match(r'\p{{script={0}}}$'.format(script), s) for s in (chr(cp) for cp, cpd in sc.items() if script == cpd['Script'] and cp <= 0xFFFF))
        else:
            assert all(regex.match(r'\p{{script={0}}}$'.format(script), s) for s in (chr(cp) for cp, cpd in sc.items() if script == cpd['Script']))

    djt = ucdf.derivedjoiningtype
    joining_types = set()
    for cp, cpd in djt.items():
        joining_types.update((cpd['Joining_Type'],))
    for joining_type in joining_types:
        if sys.maxunicode == 0xFFFF:
            assert all(regex.match(r'\p{{joining_type={0}}}'.format(joining_type), s) for s in (chr(cp) for cp, cpd in djt.items() if joining_type == cpd['Joining_Type'] and cp <= 0xFFFF))
        else:
            assert all(regex.match(r'\p{{joining_type={0}}}'.format(joining_type), s) for s in (chr(cp) for cp, cpd in djt.items() if joining_type == cpd['Joining_Type']))


def test_script_extensions():
    sce = mdl.UCDFiles().scriptextensions
    assert sce[0x1CD1]['Script_Extensions'] == {'Deva': True}
    assert sce[0x3006]['Script_Extensions'] == {'Hani': True}
    assert sce[0x0660]['Script_Extensions'] == {'Arab': True, 'Thaa': True}
    assert sce[0x09E6]['Script_Extensions'] == {'Beng': True, 'Cakm': True, 'Sylo': True}


def test_confusables():
    cfs = mdl.SecurityFiles().confusables
    assert cfs[0x05AD] == (0x0596,)
    assert cfs[0x06E8] == (0x0306, 0x0307)
    assert cfs[0x2026] == (0x002E, 0x002E, 0x002E)
    assert cfs[0x1142F] == (0x11434, 0x11442, 0x1142E)


def test_exceptions():
    with pytest.raises(TypeError):
        mdl.UCDFiles(data_path=1)
    with pytest.raises(TypeError):
        mdl.UCDFiles(unicode_version=1)


def test_data_path():
    test_path = os.path.split(os.path.realpath(__file__))[0]
    data_path = os.path.join(test_path, '..', 'unicodetools', 'data', mdl.UNICODE_VERSION)
    unicodedata_path = os.path.join(data_path, 'UnicodeData.zip')
    if os.path.isfile(unicodedata_path):
        ud_data_path = mdl.UCDFiles(data_path=data_path).unicodedata
        ud_default = mdl.UCDFiles().unicodedata
        assert ud_data_path == ud_default
    else:
        raise Exception('Could not test loading non-packaged data files')
