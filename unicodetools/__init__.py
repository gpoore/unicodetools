# -*- coding: utf-8 -*-
#
# Copyright (c) 2016-2017, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the BSD 3-Clause License:
# http://opensource.org/licenses/BSD-3-Clause
#


from .version import __version__


from .collections import (CodePointRange, codepoints_to_codepointranges,
                          CodePointMultiRange)

from .coding import chr_surrogate, ord_surrogate

from .datafiles import UNICODE_VERSION, UCDFiles, SecurityFiles
ucd = UCDFiles()
security = SecurityFiles()
