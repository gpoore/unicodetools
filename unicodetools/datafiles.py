# -*- coding: utf-8 -*-
#
# Copyright (c) 2016-2017, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the BSD 3-Clause License:
# http://opensource.org/licenses/BSD-3-Clause
#

'''
Extract data from files in the Unicode Character Database (UCD).

Code points are always represented as integers in the processed data.  This
avoids potential complications on narrow Python builds.

All attribute and property names follow the Unicode standard precisely,
including capitalization.  This means that some attributes or properties
have capitalized characters in their names even though they are not classes.
Similarly, namedtuples are created for data files that contain only a single
property, with names of the form `<file_name>_CodePoint`.  In the few cases
where <file_name> does not start with a capital letter, this results in a
class name that starts lowercase.
'''


# pylint: disable=C0103, C0301


from __future__ import (division, print_function, absolute_import,
                        unicode_literals)


import sys
import os
import io
import collections
import zipfile
import re
import pkgutil
import fractions
from . import coding
from . import err


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


UNICODE_VERSION = '9.0.0'




# Class for code point data extracted from UnicodeData.txt.
UnicodeData_CodePoint = collections.namedtuple('UnicodeData_CodePoint',
                                               ['Code_Point',
                                                'Name',
                                                'General_Category',
                                                'Canonical_Combining_Class',
                                                'Bidi_Class',
                                                'Decomposition_Type',
                                                'Decomposition_Mapping',
                                                'Numeric_Type',
                                                'Numeric_Value',
                                                'Bidi_Mirrored',
                                                'Unicode_1_Name',
                                                'ISO_Comment',
                                                'Simple_Uppercase_Mapping',
                                                'Simple_Lowercase_Mapping',
                                                'Simple_Titlecase_Mapping'])


# Class for data extracted from Unicode property files containing multiple
# properties per code point.  `.properties` should be a dict.  For boolean
# properties, all keys will have the value True.
Properties_CodePoint = collections.namedtuple('Properties_CodePoint',
                                              ['Code_Point', 'Properties'])


# Class generator for data extracted from Unicode property files containing
# only a single property per code point.
def _generate_single_property_namedtuple(file_name, property_name):
    return collections.namedtuple('{0}_CodePoint'.format(file_name),
                                  ['Code_Point', property_name])


# Assemble data file grammar
# This is based on Unicode Standard Annex #44: UNICODE CHARACTER DATABASE
# http://unicode.org/reports/tr44/
#
# All regexes are intended for use with re.VERBOSE, so all whitespace is
# represented explicitly.
#
# From Table 20, Common Subexpressions for Validation
ucd_subexpression_raw_regex_patterns = [('digit', r'[0-9]'),
                                        ('hexDigit', r'[A-F0-9]'),
                                        ('alphaNum', r'[a-zA-Z0-9]'),
                                        ('digits', r'{digit}+'),
                                        ('label', r'{alphaNum}+'),
                                        ('positiveDecimal', r'{digits}\.{digits}'),
                                        ('decimal', r'-?{positiveDecimal}'),
                                        ('rational', r'-?{digits}(?:/{digits})?'),
                                        ('optionalDecimal', r'-?{digits}(?:\.{digits})?'),
                                        ('name', r'{label}(?:(?:\x20-|-\x20|[-_\x20]){label})*'),
                                        ('name2', r'{label}(?:[-_\x20]{label})*'),
                                        ('annotatedName', r'{name2}(?:\x20\(.*\))?'),
                                        ('shortName', r'[A-Z]{{0,3}}'),
                                        ('codePoint', r'(?:10|{hexDigit})?{hexDigit}{{4}}'),
                                        ('codePoints', r'{codePoint}(?:\x20{codePoint})*'),
                                        ('codePoint0', r'{codePoints}?')]

ucd_subexpression_regex_patterns = {}
for k, v in ucd_subexpression_raw_regex_patterns:
    ucd_subexpression_regex_patterns[k] = v.format(**ucd_subexpression_regex_patterns)

# From Table 21, Regular Expressions for Other Property Values
ucd_property_raw_regex_patterns = [('nv', 'Numeric_Value', r'{decimal}|{optionalDecimal}|{rational}'),
                                   ('blk', 'Block', r'{name2}'),
                                   ('sc', 'Script', r'{name2}'),
                                   ('dm', 'Decomposition_Mapping', r'{codePoints}'),
                                   ('FC_NFKC', 'FC_NFKC_Closure', r'{codePoints}'),
                                   ('NFKC_CF', 'NFKC_Casefold', r'{codePoint0}'),
                                   ('cf', 'Case_Folding', r'{codePoints}'),
                                   ('lc', 'Lowercase_Mapping', r'{codePoints}'),
                                   ('tc', 'Titlecase_Mapping', r'{codePoints}'),
                                   ('uc', 'Uppercase_Mapping', r'{codePoints}'),
                                   ('sfc', 'Simple_Case_Folding', r'{codePoint}'),
                                   ('slc', 'Simple_Lowercase_Mapping', r'{codePoint}'),
                                   ('stc', 'Simple_Titlecase_Mapping', r'{codePoint}'),
                                   ('suc', 'Simple_Uppercase_Mapping', r'{codePoint}'),
                                   ('bmg', 'Bidi_Mirroring_Glyph', r'{codePoint}'),
                                   ('na', 'Name', r'{name}'),
                                   ('Name_Alias', 'Name_Alias', r'{name}'),
                                   ('na1', 'Unicode_1_Name', r'{annotatedName}'),
                                   ('JSN', 'Jamo_Short_Name', r'{shortName}')]

ucd_property_regex_patterns = {}
for alias, k, v in ucd_property_raw_regex_patterns:
    ucd_property_regex_patterns[alias] = ucd_property_regex_patterns[k] = v.format(**ucd_subexpression_regex_patterns)

# Additional patterns useful in validation.
# General_Category from Table 12, General_Category Values
# Bidi_Class from Table 13, Bidi_Class Values
ucd_other_raw_regex_patterns = [('gc', 'General_Category_Abbr',
                                 r'C|Cc|Cf|Cn|Co|Cs|L|LC|Ll|Lm|Lo|Lt|Lu|M|Mc|Me|Mn|N|Nd|Nl|No|P|Pc|Pd|Pe|Pf|Pi|Po|Ps|S|Sc|Sk|Sm|So|Z|Zl|Zp|Zs'),
                                ('bc', 'Bidi_Class_Abbr',
                                 r'L|R|AL|EN|ES|ET|AN|CS|NSM|BN|B|S|WS|ON|LRE|LRO|RLE|RLO|PDF|LRI|RLI|FSI|PDI')]

ucd_other_regex_patterns = {}
for alias, k, v in ucd_other_raw_regex_patterns:
    ucd_other_regex_patterns[alias] = ucd_other_regex_patterns[k] = v.format(**ucd_subexpression_regex_patterns)

# Generic Property and Value regexes aren't defined in the Unicode
# specification, so relatively strict ones are defined here.
ucd_regex_patterns = {'Generic_Property': r'[A-Z]+[a-z]*(_[A-Z]+[a-z]*)*|[A-Z][a-z]+[A-Z][a-z]+',
                      'Generic_Value': r'[A-Z]+[a-z]*(_[A-Z]+[a-z]*)*|[A-Z][a-z]+[A-Z][a-z]+'}
for d in (ucd_subexpression_regex_patterns, ucd_property_regex_patterns, ucd_other_regex_patterns):
    for k in d:
        if k in ucd_regex_patterns:
            raise err.DataError('Duplicate regex data')
    ucd_regex_patterns.update(d)




class UCDFiles(object):
    '''
    Interface for files in the Unicode Character Database (UCD).

    By default, Unicode 9.0.0 data files are loaded.  If `unicode_version` is
    specified, the corresponding version will be used if it exists in the
    package data directory.  Files outside the package directory may also be
    used by providing `data_path`.  Note that data files for other versions
    must currently have a format that is strictly compatible with 9.0.0.

    To maximize performance, all data files are only loaded on use.
    '''
    def __init__(self, unicode_version=None, data_path=None):
        if unicode_version is not None and data_path is not None:
            raise err.InitError('Options "unicode_version" and "data_path" are mutually exclusive')
        if any(x is not None and not isinstance(x, str) for x in (unicode_version, data_path)):
            raise err.InitError('Options "unicode_version" and "data_path" must be None or strings')
        self.unicode_version = unicode_version
        self.data_path = data_path

        self._Blocks = None
        self._confusables = None
        self._DerivedBidiClass = None
        self._DerivedCoreProperties = None
        self._DerivedEastAsianWidth = None
        self._DerivedJoiningType = None
        self._DerivedNumericType = None
        self._DerivedNumericValues = None
        self._EastAsianWidth = None
        self._PropList = None
        self._ScriptExtensions = None
        self._Scripts = None
        self._UnicodeData = None


    def _load_ucd_data(self, fname):
        '''
        Load UCD data file, either from the package data directory or from
        a specified data path.
        '''
        if self.data_path is not None:
            fpath_fname = os.path.join(self.data_path, fname)
            if os.path.isfile('{0}.zip'.format(fpath_fname)):
                with zipfile.ZipFile('{0}.zip'.format(fpath_fname)) as z:
                    if '{0}.txt'.format(fname) in z.namelist():
                        with z.open('{0}.txt'.format(fname)) as f:
                            raw_data = f.read()
                    else:
                        raise err.InitError('Could not find data file "{0}.txt" in zip archive "{1}.zip"'.format(fname, fpath_fname))
            elif os.path.isfile('{0}.txt'.format(fpath_fname)):
                with open('{0}.txt'.format(fpath_fname), 'rb') as f:
                    raw_data = f.read()
            else:
                raise err.InitError('Could not find data file "{0}" in .txt or .zip forms in directory "{1}"'.format(fname, self.data_path))
        else:
            if self.unicode_version is None:
                unicode_version = UNICODE_VERSION
            else:
                unicode_version = self.unicode_version
            zipped_raw_data = pkgutil.get_data('unicodetools', 'data/{0}/{1}.zip'.format(unicode_version, fname))
            if zipped_raw_data is None:
                raise err.DataError('Could not find unicodetools package data file "data/{0}/{1}.zip"'.format(unicode_version, fname))
            with zipfile.ZipFile(io.BytesIO(zipped_raw_data)) as z:
                with z.open('{0}.txt'.format(fname)) as f:
                    raw_data = f.read()
        # Use codec that can handle BOM, to deal with "confusables.txt" and
        # possibly other files.
        data = raw_data.decode('utf_8_sig')
        return data


    # Tables for deriving Hangul syllable names.
    _JAMO_L_TABLE = ('G', 'GG', 'N', 'D', 'DD', 'R', 'M', 'B', 'BB',
                     'S', 'SS', '', 'J', 'JJ', 'C', 'K', 'T', 'P', 'H')
    _JAMO_V_TABLE = ('A', 'AE', 'YA', 'YAE', 'EO', 'E', 'YEO', 'YE', 'O',
                     'WA', 'WAE', 'OE', 'YO', 'U', 'WEO', 'WE', 'WI',
                     'YU', 'EU', 'YI', 'I')
    _JAMO_T_TABLE = ('', 'G', 'GG', 'GS', 'N', 'NJ', 'NH', 'D', 'L', 'LG', 'LM',
                     'LB', 'LS', 'LT', 'LP', 'LH', 'M', 'B', 'BS',
                     'S', 'SS', 'NG', 'J', 'C', 'K', 'T', 'P', 'H')

    @classmethod
    def hangul_syllable_name(cls, cp):
        '''
        Algorithmically determine the name for a Hangul Syllable.

        This code is a direct translation of the algorithm given in
        The Unicode Standard, Version 9.0, Chapter 3.12, in the section
        "Sample Code for Hangul Algorithms."
        '''
        cp_index = cp - 0xAC00
        if cp_index < 0 or cp_index >= 11172:
            raise err.ValueError('The code point {0:04X} is not a Hangul Syllable'.format(cp))
        l_index = cp_index // 588
        v_index = (cp_index % 588) // 28
        t_index = cp_index % 28
        return 'HANGUL SYLLABLE {0}{1}{2}'.format(cls._JAMO_L_TABLE[l_index],
                                                  cls._JAMO_V_TABLE[v_index],
                                                  cls._JAMO_T_TABLE[t_index])


    @classmethod
    def hangul_syllable_decomposition_mapping(cls, cp):
        '''
        Decompose a Hangul Syllable to obtain the Decomposition_Mapping.

        This code is a combination of the decomposition and composition
        algorithms given in The Unicode Standard, Version 9.0, Chapter 3.12,
        in the section "Sample Code for Hangul Algorithms."  The code
        decomposes <LV> syllables into <L, V> and <LVT> syllables into
        <LV, T>, in accordance with the section "Hangul Syllable
        Decomposition."
        '''
        cp_index = cp - 0xAC00
        if cp_index < 0 or cp_index >= 11172:
            raise err.ValueError('The code point {0:04X} is not a Hangul Syllable'.format(cp))
        cp_t = 0x11A7 + cp_index % 28
        if cp_t != 0x11A7:
            # Using integer arithmetic here, so can't simplify math further
            cp_lv = 0xAC00 + (cp_index // 588 * 21 + (cp_index % 588) // 28) * 28
            decomposition_mapping = (cp_lv, cp_t)
        else:
            cp_l = 0x1100 + cp_index // 588
            cp_v = 0x1161 + (cp_index % 588) // 28
            decomposition_mapping = (cp_l, cp_v)
        return decomposition_mapping


    _unicodedata_pattern = r'''
                            (?P<Code_Point> {codePoint});
                            (?P<Name> {name}|<{name}(?:,\x20(?:First|Last))?>);
                            (?P<General_Category> {General_Category_Abbr});
                            (?P<Canonical_Combining_Class> {name});
                            (?P<Bidi_Class> {Bidi_Class_Abbr});
                            (?: (?:<(?P<Decomposition_Type> {name})>\x20)? (?P<Decomposition_Mapping> {Decomposition_Mapping}) )?;
                            (?P<Numeric> ;;|{digits};{digits};{digits}|;{digits};{digits}|;;{rational});
                            (?P<Bidi_Mirrored> Y|N);
                            (?P<Unicode_1_Name> {annotatedName}|);
                            (?P<ISO_Comment>);
                            (?P<Simple_Uppercase_Mapping> {Simple_Uppercase_Mapping})?;
                            (?P<Simple_Lowercase_Mapping> {Simple_Lowercase_Mapping})?;
                            (?P<Simple_Titlecase_Mapping> {Simple_Titlecase_Mapping})?
                            \s*$
                            '''.format(**ucd_regex_patterns)

    _unicodedata_re = re.compile(_unicodedata_pattern, re.VERBOSE)


    @property
    def UnicodeData(self):
        '''
        Data from UnicodeData.txt.
        '''
        if self._UnicodeData is None:
            data = self._load_ucd_data('UnicodeData')
            unicodedata = collections.OrderedDict()
            try:
                # Create an iterator, so that when the first line of a code
                # point range is encountered, `next()` can be used to look
                # ahead to the last line of the range.
                line_iter = iter(data.splitlines())
                for line in line_iter:
                    gd = self._unicodedata_re.match(line).groupdict()
                    # Defaults values according to Unicode Standard Annex #44,
                    # Table 4 and elsewhere
                    # http://unicode.org/reports/tr44/#Format_Conventions
                    gd['Code_Point'] = int(gd['Code_Point'], 16)
                    # Process Name later, because that makes it more
                    # convenient to deal with ranges.
                    if gd['Decomposition_Type'] is None:
                        gd['Decomposition_Type'] = 'Canonical'
                    if gd['Decomposition_Mapping'] is None:
                        gd['Decomposition_Mapping'] = (gd['Code_Point'],)
                    else:
                        gd['Decomposition_Mapping'] = tuple(int(x, 16) for x in gd['Decomposition_Mapping'].split('\x20'))
                    numeric = gd['Numeric']
                    del gd['Numeric']  # Not a valid field name for namedtuple
                    # Numeric_Value is always stored as a string rather than
                    # being converted to an int, float, fractions.Fraction,
                    # etc.  This gives users access to the raw data while
                    # preventing any loss of precision or preferring a
                    # particular rational number implementation.
                    if numeric == ';;':
                        gd['Numeric_Type'] = 'None'
                        gd['Numeric_Value'] = 'NaN'
                    elif numeric.startswith(';;'):
                        gd['Numeric_Type'] = 'Numeric'
                        gd['Numeric_Value'] = numeric.rsplit(';', 1)[1]
                    elif numeric.startswith(';'):
                        gd['Numeric_Type'] = 'Digit'
                        gd['Numeric_Value'] = numeric.rsplit(';', 1)[1]
                    else:
                        gd['Numeric_Type'] = 'Decimal'
                        gd['Numeric_Value'] = numeric.rsplit(';', 1)[1]
                    if gd['Bidi_Mirrored'] == 'Y':
                        gd['Bidi_Mirrored'] = True
                    else:
                        gd['Bidi_Mirrored'] = False
                    if gd['Simple_Uppercase_Mapping'] is None:
                        gd['Simple_Uppercase_Mapping'] = gd['Code_Point']
                    else:
                        gd['Simple_Uppercase_Mapping'] = int(gd['Simple_Uppercase_Mapping'], 16)
                    if gd['Simple_Lowercase_Mapping'] is None:
                        gd['Simple_Lowercase_Mapping'] = gd['Code_Point']
                    else:
                        gd['Simple_Lowercase_Mapping'] = int(gd['Simple_Lowercase_Mapping'], 16)
                    if gd['Simple_Titlecase_Mapping'] is None:
                        gd['Simple_Titlecase_Mapping'] = gd['Simple_Uppercase_Mapping']
                    else:
                        gd['Simple_Titlecase_Mapping'] = int(gd['Simple_Titlecase_Mapping'], 16)
                    udcp = UnicodeData_CodePoint(**gd)
                    if not udcp.Name.startswith('<'):
                        unicodedata[udcp.Code_Point] = udcp
                    else:
                        if udcp.Name == '<control>':
                            unicodedata[udcp.Code_Point] = udcp._replace(Name='')
                        else:
                            if not udcp.Name.endswith(',\x20First>'):
                                raise err.DataError('Invalid unnamed code point or invalid code point range:\n  "{0}"'.format(line))
                            first = udcp.Code_Point
                            base_name = udcp.Name.strip('<>').rsplit(',', 1)[0]
                            next_line = next(line_iter)
                            gd_last = self._unicodedata_re.match(next_line).groupdict()
                            if not gd_last['Name'].endswith(',\x20Last>') or gd_last['Name'].strip('<>').rsplit(',', 1)[0] != base_name:
                                raise err.DataError('Invalid code point range:\n  "{0}"'.format(next_line))
                            last = int(gd_last['Code_Point'], 16)
                            if 'Surrogate' in base_name or 'Private' in base_name:
                                for cp in range(first, last+1):
                                    unicodedata[cp] = udcp._replace(Code_Point=cp,
                                                                    Name='',
                                                                    Decomposition_Mapping=(cp,),
                                                                    Simple_Uppercase_Mapping=cp,
                                                                    Simple_Lowercase_Mapping=cp,
                                                                    Simple_Titlecase_Mapping=cp)
                            elif base_name == 'Hangul Syllable':
                                # See UAX #44, as well as the parts of The
                                # Unicode Standard, Version 9.0, Chapter 3.12
                                # that are referenced in the Hangul functions
                                for cp in range(first, last+1):
                                    unicodedata[cp] = udcp._replace(Code_Point=cp,
                                                                    Name=self.hangul_syllable_name(cp),
                                                                    Decomposition_Mapping=self.hangul_syllable_decomposition_mapping(cp),
                                                                    Simple_Uppercase_Mapping=cp,
                                                                    Simple_Lowercase_Mapping=cp,
                                                                    Simple_Titlecase_Mapping=cp)
                            else:
                                # Naming from The Unicode Standard, Version 9.0, Chapter 4.8, section "Unicode Name Property".
                                # Don't have to check `first in (0xF900, 0xFA70, 0x2F800)` for 'CJK COMPATIBILITY IDEOGRAPH',
                                # since those code points are listed individually in UnicodeData.txt.
                                if first in (0x3400, 0x4E00, 0x20000, 0x2A700, 0x2B740, 0x2B820):
                                    base_name = 'CJK UNIFIED IDEOGRAPH'
                                elif first == 0x17000:
                                    base_name = 'TANGUT IDEOGRAPH'
                                else:
                                    raise err.DataError('Unknown name for code point range U+{0:04X} - U+{1:04X}'.format(first, last))
                                for cp in range(first, last+1):
                                    unicodedata[cp] = udcp._replace(Code_Point=cp,
                                                                    Name='{0}-{1:04X}'.format(base_name, cp),
                                                                    Decomposition_Mapping=(cp,),
                                                                    Simple_Uppercase_Mapping=cp,
                                                                    Simple_Lowercase_Mapping=cp,
                                                                    Simple_Titlecase_Mapping=cp)
                # Update to account for derived numeric data
                derived_numeric_type = self.DerivedNumericType
                derived_numeric_values = self.DerivedNumericValues
                for cp, nt in derived_numeric_type.items():
                    if unicodedata[cp].Numeric_Type == 'None':
                        unicodedata[cp] = unicodedata[cp]._replace(Numeric_Type=nt.Numeric_Type,
                                                                   Numeric_Value=derived_numeric_values[cp].Numeric_Value)
                    elif (unicodedata[cp].Numeric_Type != nt.Numeric_Type or
                          fractions.Fraction(unicodedata[cp].Numeric_Value) != fractions.Fraction(derived_numeric_values[cp].Numeric_Value)):
                        msg = 'Mismatched "Numeric_Type" and/or "Numeric_Value" between "UnicodeData.txt" and "DerivedNumericType.txt" or "DerivedNumericValues.txt."'
                        msg += '\n  {0}, {1} vs. {2}, {3}'.format(unicodedata[cp].Numeric_Type,
                                                                  unicodedata[cp].Numeric_Value,
                                                                  nt.Numeric_Type,
                                                                  derived_numeric_values[cp].Numeric_Value)
                        raise err.DataError(msg)
            except Exception as e:
                raise err.DataError('Failed to parse UnicodeData.txt:\n  {0}'.format(e))
            self._UnicodeData = unicodedata
        return self._UnicodeData


    _codepoint_single_property_line_re = re.compile(r'(?P<Code_Point>{codePoint}|{codePoint}\.\.{codePoint})\s*;\s*(?P<Property>{Generic_Property})\s*#.*$'.format(**ucd_regex_patterns))


    def _get_multiple_boolean_properties(self, properties_file):
        '''
        Load and process a properties file containing multiple properties
        per code point with boolean values.
        '''
        data = self._load_ucd_data(properties_file)
        cp_properties = collections.OrderedDict()
        for line in data.splitlines():
            line = line.strip()
            if line and line[:1] != '#':
                gd = self._codepoint_single_property_line_re.match(line).groupdict()
                codepoint = gd['Code_Point']
                prop = gd['Property']
                if '..' in codepoint:
                    first, last = codepoint.split('..')
                    for cp in range(int(first, 16), int(last, 16)+1):
                        if cp not in cp_properties:
                            cp_properties[cp] = Properties_CodePoint(cp, collections.OrderedDict())
                        cp_properties[cp].Properties[prop] = True
                else:
                    cp = int(codepoint, 16)
                    if cp not in cp_properties:
                        cp_properties[cp] = Properties_CodePoint(cp, collections.OrderedDict())
                    cp_properties[cp].Properties[prop] = True
        return cp_properties


    _codepoint_single_value_line_re = re.compile(r'(?P<Code_Point>{codePoint}|{codePoint}\.\.{codePoint})\s*;\s*(?P<Value>{Generic_Value})\s*#.*$'.format(**ucd_regex_patterns))


    def _get_single_string_property(self, property_file, property_name, postprocess=None, line_re=None):
        '''
        Load and process a properties file containing a single property
        per code point with string values.

        Keyword arguments `postprocess` and `line_re` allow a special
        processing function and a special line regex to be specified.
        '''
        data = self._load_ucd_data(property_file)
        cp_property = collections.OrderedDict()
        property_namedtuple = _generate_single_property_namedtuple(property_file, property_name)
        if postprocess is not None and not hasattr(postprocess, '__call__'):
            raise err.InitError('Invalid argument "postprocess"; must be callable')
        if line_re is None:
            line_re = self._codepoint_single_value_line_re
        for line in data.splitlines():
            line = line.strip()
            if line and line[:1] != '#':
                gd = line_re.match(line).groupdict()
                codepoint = gd['Code_Point']
                if '..' in codepoint:
                    first, last = codepoint.split('..')
                    for cp in range(int(first, 16), int(last, 16)+1):
                        if cp in cp_property:
                            raise err.DataError('Multiple properties encountered for U+{0:04X}; only a single property was expected'.format(cp))
                        if postprocess is not None:
                            cp_property[cp] = property_namedtuple(cp, postprocess(gd))
                        else:
                            cp_property[cp] = property_namedtuple(cp, gd['Value'])
                else:
                    cp = int(codepoint, 16)
                    if cp in cp_property:
                        raise err.DataError('Multiple properties encountered for U+{0:04X}; only a single property was expected'.format(cp))
                    if postprocess is not None:
                        cp_property[cp] = property_namedtuple(cp, postprocess(gd))
                    else:
                        cp_property[cp] = property_namedtuple(cp, gd['Value'])
        return cp_property


    _blocks_line_re = re.compile(r'(?P<Code_Point>{codePoint}|{codePoint}\.\.{codePoint})\s*;\s*(?P<Value>{Block})$'.format(**ucd_regex_patterns))


    @property
    def Blocks(self):
        '''
        Data from Blocks.txt.
        '''
        if self._Blocks is None:
            self._Blocks = self._get_single_string_property('Blocks', 'Block', line_re=self._blocks_line_re)
        return self._Blocks


    _confusables_line_re = re.compile(r'(?P<Code_Point>{codePoint})\s*;\s*(?P<confusable>{codePoints})\s*;\s*MA\s*#.*$'.format(**ucd_regex_patterns))


    @property
    def confusables(self):
        '''
        Data from confusables.txt.
        '''
        if self._confusables is None:
            self._confusables = self._get_single_string_property('confusables', 'confusable',
                                                                 postprocess=lambda gd: tuple(int(x, 16) for x in gd['confusable'].split('\x20')),
                                                                 line_re=self._confusables_line_re)
        return self._confusables


    @property
    def DerivedBidiClass(self):
        '''
        Data from DerivedBidiClass.txt.
        '''
        if self._DerivedBidiClass is None:
            self._DerivedBidiClass = self._get_single_string_property('DerivedBidiClass', 'Bidi_Class')
        return self._DerivedBidiClass


    @property
    def DerivedCoreProperties(self):
        '''
        Data from DerivedCoreProperties.txt.
        '''
        if self._DerivedCoreProperties is None:
            self._DerivedCoreProperties = self._get_multiple_boolean_properties('DerivedCoreProperties')
        return self._DerivedCoreProperties


    @property
    def DerivedEastAsianWidth(self):
        '''
        Data from DerivedEastAsianWidth.txt.
        '''
        if self._DerivedEastAsianWidth is None:
            self._DerivedEastAsianWidth = self._get_single_string_property('DerivedEastAsianWidth', 'East_Asian_Width')
        return self._DerivedEastAsianWidth


    @property
    def DerivedJoiningType(self):
        '''
        Data from DerivedJoiningType.txt.
        '''
        if self._DerivedJoiningType is None:
            self._DerivedJoiningType = self._get_single_string_property('DerivedJoiningType', 'Joining_Type')
        return self._DerivedJoiningType


    @property
    def DerivedNumericType(self):
        '''
        Data from DerivedNumericType.txt.
        '''
        if self._DerivedNumericType is None:
            self._DerivedNumericType = self._get_single_string_property('DerivedNumericType', 'Numeric_Type')
        return self._DerivedNumericType


    _derived_numeric_values_line_re = re.compile(r'(?P<Code_Point>{codePoint}|{codePoint}\.\.{codePoint})\s*;\s*{decimal}\s*;\s*;\s*(?P<Value>{rational})\s*#.*$'.format(**ucd_regex_patterns))


    @property
    def DerivedNumericValues(self):
        '''
        Data from DerivedNumericValues.txt.
        '''
        if self._DerivedNumericValues is None:
            self._DerivedNumericValues = self._get_single_string_property('DerivedNumericValues', 'Numeric_Value', line_re=self._derived_numeric_values_line_re)
        return self._DerivedNumericValues


    @property
    def EastAsianWidth(self):
        '''
        Data from EastAsianWidth.txt.
        '''
        if self._EastAsianWidth is None:
            self._EastAsianWidth = self._get_single_string_property('EastAsianWidth', 'East_Asian_Width')
        return self._EastAsianWidth


    @property
    def PropList(self):
        '''
        Data from PropList.txt.
        '''
        if self._PropList is None:
            self._PropList = self._get_multiple_boolean_properties('PropList')
        return self._PropList


    _script_extensions_line_re = re.compile(r'(?P<Code_Point>{codePoint}|{codePoint}\.\.{codePoint})\s*;\s*(?P<Scripts>{Script}(\x20{Script})*)\s*#.*$'.format(**ucd_regex_patterns))


    @property
    def ScriptExtensions(self):
        '''
        Data from ScriptExtensions.txt.
        '''
        def postprocess(re_match_groupdict):
            ret = collections.OrderedDict()
            for key in re_match_groupdict['Scripts'].split('\x20'):
                ret[key] = True
            return ret
        if self._ScriptExtensions is None:
            self._ScriptExtensions = self._get_single_string_property('ScriptExtensions', 'Script_Extensions',
                                                                      postprocess=postprocess,
                                                                      line_re=self._script_extensions_line_re)
        return self._ScriptExtensions


    @property
    def Scripts(self):
        '''
        Data from Scripts.txt.
        '''
        if self._Scripts is None:
            self._Scripts = self._get_single_string_property('Scripts', 'Script')
        return self._Scripts
