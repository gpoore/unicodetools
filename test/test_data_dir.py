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
import pytest
if sys.version_info.major == 2:
    import urllib2
else:
    import urllib.request
import hashlib
import pkgutil
import io
import zipfile


TEST_AGAINST_REMOTE_UNICODE_ORG = False




def test_data_dir():
    '''
    Test all files in the package data directory for correct sha256 sums.

    Hashes were obtained using the function defined below.
    '''
    def hash_remote_file(url):
        '''
        Download file specified by `url` and return sha256 hex.
        '''
        if sys.version_info.major == 2:
            fdata = urllib2.urlopen(url).read()
        else:
            with urllib.request.urlopen(url) as response:
                fdata = response.read()
        h = hashlib.sha256()
        h.update(fdata)
        return h.hexdigest()

    ucd_files = {'Blocks.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/Blocks.txt',
                                'sha256': '612127d4889032e55d82522e4a0c19793bda8aa8da14ecb3c696d17c83e6be13'},
                 'DerivedBidiClass.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/extracted/DerivedBidiClass.txt',
                                          'sha256': '73573a4bee7f7377d936bc1710cd578001d00ba516e72ee54e906ae51a8c1fcb'},
                 'DerivedCoreProperties.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/DerivedCoreProperties.txt',
                                               'sha256': '6662c7e30b572df5d948c092692f52bcc79ab36d49a063a73d6435042db6fb3b'},
                 'DerivedEastAsianWidth.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/extracted/DerivedEastAsianWidth.txt',
                                               'sha256': 'e17138d36cd91f0e0d16437780a887c5ac637bde0de370b96f08a3424fcc322f'},
                 'DerivedJoiningType.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/extracted/DerivedJoiningType.txt',
                                            'sha256': '3a8f8642084ed23b0de52af72dea0ff3d0b6928e6c7442832c663899e2b85e9d'},
                 'DerivedNumericType.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/extracted/DerivedNumericType.txt',
                                            'sha256': 'ef24061b5a5dc93d7e90c2e34530ec757180ee75d872cba65ffc946e52624ae8'},
                 'DerivedNumericValues.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/extracted/DerivedNumericValues.txt',
                                              'sha256': 'a197371fec9a1b517058b440841f60f9378d81682084eef8db22a88cb2f96e90'},
                 'EastAsianWidth.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/EastAsianWidth.txt',
                                        'sha256': '3382cb4980e0021e9d4312f2d099315cfab6100ce0ff63a22d6937bfa720bcb7'},
                 'PropList.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/PropList.txt',
                                  'sha256': 'f413ea8dbd3858de72f3148b47dd0586019761357d1481e3b65f3a025bc27f82'},
                 'ScriptExtensions.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/ScriptExtensions.txt',
                                          'sha256': 'cde011921972dffe3e30dcbc7afbf069bf2eb01269097111dd7533b4c524caac'},
                 'Scripts.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/Scripts.txt',
                                 'sha256': 'fba415952f5654145acad220dc2b878f815c673474d2bb4928934e3ba6ccca1d'},
                 'UnicodeData.txt': {'url': 'http://www.unicode.org/Public/9.0.0/ucd/UnicodeData.txt',
                                     'sha256': '68dfc414d28257b9b5d6ddbb8b466c768c00ebdf6cbf7784364a9b6cad55ee8f'}}

    security_files = {'confusables.txt': {'url': 'http://www.unicode.org/Public/security/9.0.0/confusables.txt',
                                          'sha256': '27339d1807fcdc8606ca11866d02238fa2729dc590bd1a24f356d985f28a9977'}}

    files = ucd_files.copy()
    files.update(security_files)

    unicode_version = mdl.UNICODE_VERSION
    for fname, fdata in files.items():
        zipped_raw_data = pkgutil.get_data('unicodetools', 'data/{0}/{1}.zip'.format(unicode_version, fname.rsplit('.', 1)[0]))
        assert zipped_raw_data is not None
        with zipfile.ZipFile(io.BytesIO(zipped_raw_data)) as z:
            with z.open(fname) as f:
                raw_data = f.read()
        h = hashlib.sha256()
        h.update(raw_data)
        assert h.hexdigest() == fdata['sha256']
        if TEST_AGAINST_REMOTE_UNICODE_ORG:
            remote_sha256 = hash_remote_file(fdata['url'])
            assert h.hexdigest() == remote_sha256
