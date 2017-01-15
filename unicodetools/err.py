# -*- coding: utf-8 -*-
#
# Copyright (c) 2016-2017, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the BSD 3-Clause License:
# http://opensource.org/licenses/BSD-3-Clause
#

'''
Exceptions for unicodetools.
'''


class UnicodeToolsError(Exception):
    '''
    Base unicodetools error.
    '''
    pass


class DataError(UnicodeToolsError):
    '''
    Error in internal or loaded data.
    '''
    pass
