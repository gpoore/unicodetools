================
``unicodetools``
================


The ``unicodetools`` package provides an interface for working with the
`Unicode Character Database (UCD) <http://unicode.org/reports/tr44/>`_ and
other Unicode data files.  Python's standard library contains the
`unicodedata module <https://docs.python.org/3.6/library/unicodedata.html>`_,
which provides access to a subset of the data in the UCD for a particular
Unicode version.  For example, Python 2.7 uses Unicode 5.2.0, Python 3.5
uses 8.0.0, and Python 3.6 uses 9.0.0.  The ``unicodetools`` package
provides access to the most recent UCD data from Unicode 9.0.0, and includes
data not available in ``unicodedata``.

``unicodetools`` also provides versions of ``chr()`` and ``ord()`` that work
with Unicode surrogate code point pairs, and tools for assembling regular
expression patterns that may be compiled with the
`re module <https://docs.python.org/3/library/re.html>`_.


.. contents::


Unicode Character Database (UCD)
================================

``unicodetools.ucd`` has attributes corresponding to the following data
files.  Attribute names correspond to lower case versions of the file names
with the ``.txt`` extension removed.

*  ``Blocks.txt``
*  ``DerivedBidiClass.txt``
*  ``DerivedCoreProperties.txt``
*  ``DerivedEastAsianWidth.txt``
*  ``DerivedJoiningType.txt``
*  ``DerivedNumericType.txt``
*  ``DerivedNumericValues.txt``
*  ``EastAsianWidth.txt``
*  ``PropList.txt``
*  ``ScriptExtensions.txt``
*  ``Scripts.txt``
*  ``UnicodeData.txt``

The attribute for each file is a ``dict`` mapping each code point to a
``dict`` of property-value pairs.  Code points are always represented as
integers, to avoid issues with Unicode surrogates under narrow Python builds.
While a property-value mapping is somewhat redundant for a file that contains
only data for a single property, this ensures that all UCD data shares a
common format.  This also requires that property names be used explicitly,
which may be useful in cases when property names might not be easily inferred
from data file names.

An example of a data file containing only a single property:

.. code::

   >>> import unicodetools
   >>> unicodetools.ucd.blocks[0]
   {'Block': 'Basic Latin'}
   >>> unicodetools.ucd.blocks[0]['Block']
   'Basic Latin'

An example of a data file containing multiple properties:

.. code::

   >>> import unicodetools
   >>> unicodetools.ucd.proplist[ord('A')]
   {'ASCII_Hex_Digit': True, 'Hex_Digit': True}

Users are strongly encouraged to consult
`UAX #44: Unicode Character Database <http://unicode.org/reports/tr44/>`_
when working with the UCD data.  This is especially true for working with
``UnicodeData.txt``, since ``unicodetools`` explicitly provides the default
values from UAX #44, rather than leaving these empty.

All boolean property values are represented as ``True``/``False``.  All
property values corresponding to single code points are represented as
single integers.  Values corresponding to a series of code points are
represented as a tuple of integers.  All other values, including numeric
values, are represented as strings.  Numeric values are not converted to a
numeric type by default, because integers, floats, and rational numbers
would be required to represent the full range of numeric values, and because
some information can be lost in the conversion to a number (for example,
"1/6" vs. "2/12").

Note that there are some differences between ``unicodedata`` and
``unicodetools.ucd``, since ``unicodetools`` explicitly provides default
values.  While ``unicodedata`` provides raw ``decimal``, ``digit``, and
``numeric`` values, ``unicodetools`` processes these values into Numeric_Type
and Numeric_Value in accordance with UAX #44.  ``unicodedata`` lacks names
for the Tangut ideographs and lacks Decomposition_Mapping for the Hangul
syllables.



UTS #39: Unicode Security Mechanisms
====================================

``unicodetools.security`` provides access to data from
`UTS #39: Unicode Security Mechanisms <http://www.unicode.org/reports/tr39/>`_.
Currently, only ``confusables.txt`` is supported.  As with the UCD data,
code points are represented as integers, and a series of code points as a
tuple of integers.  For example,

.. code::

   >>> import unicodetools
   >>> unicodetools.security.confusables[ord("`")]
   (39,)
   >>> chr(39)
   "'"



``chr_surrogate()`` and ``ord_surrogate()``
===========================================

Versions of ``chr()`` and ``ord()`` that work with Unicode surrogate code
point pairs are provided.  This is useful when working with a narrow Python
build or a system with a string implementation based on UTF-16.

.. code::

   >>> import unicodetools
   >>> unicodetools.chr_surrogate(0x10FFFF)
   '\udbff\udfff'
   >>> unicodetools.ord_surrogate('\udbff\udfff')
   1114111
   >>> hex(1114111)
   '0x10ffff'



Regular expression utilities
============================

With the interface to the UCD, it is easy to collect a list of all codepoints
with a given property.  Utilities are provided for converting such a list
into a regular expression pattern suitable for compiling with the ``re``
module.


``CodePointRange`` class
------------------------

The ``CodePointRange`` class is used to represent a range of code points.
``CodePointRange(<first>, <last>)`` represents all code points from ``first``
up to and including ``last``.  Integers or strings may be used to create a
``CodePointRange`` instance; the ``first`` and ``last`` attributes are always
integers.  The optional argument ``unpaired_surrogates=True`` is required to
allow unpaired surrogate code points (U+D800 - U+DFFF) in a range.

There are several methods for converting a ``CodePointRange`` instance into a
regular expression.

*  ``as_generic_re_pattern()`` returns a generic regular expression pattern.
   Optional boolean keyword argument ``surrogate_pairs`` causes all code
   points above 0xFFFF to be represented with surrogate pairs.  Optional
   keyword argument ``escape_func`` allows an escape function to be specified
   for escaping code points; by default, ``\uXXXX`` and ``\UXXXXXXXX``
   escapes are used for all code points except for ``0-9``, ``A-Z``, and
   ``a-z``.  If specified, ``escape_func`` must take integers.

*  ``as_python_3_3_plus_re_pattern()`` returns a regular expression pattern
   suitable for compiling with ``re`` under Python 3.3+.

*  ``as_python_before_3_3_re_pattern(surrogate_pairs=<boolean>)`` returns a
   regular expression pattern suitable for Python < 3.3.  The boolean
   keyword argument ``surrogate_pairs`` is required; it specifies narrow vs.
   wide Python builds (see ``sys.maxunicode``).

*  ``as_current_python_version_re_pattern()`` detects the version of Python
   currently in use and returns an appropriate regular expression pattern.

.. code::

   >>> import unicodetools
   >>> r = unicodetools.CodePointRange('A', 'Z')
   >>> r.as_generic_re_pattern()
   '[A-Z]'


``codepoints_to_codepointranges()`` function
--------------------------------------------

The ``codepoints_to_codepointranges()`` function converts one or more
sequences of code points, represented as integers or strings, into a list of
``CodePointRange`` objects that is sorted in order of ascending code points.
The optional boolean keyword argument ``unpaired_surrogates=True`` is
required to enable unpaired surrogate code points.

.. code::

   >>> import unicodetools
   >>> ascii_hex = []
   >>> for cp in range(0, 0x10FFFF+1):
	   if cp in unicodetools.ucd.proplist:
		   if 'ASCII_Hex_Digit' in unicodetools.ucd.proplist[cp]:
			   ascii_hex.append(cp)

   >>> len(ascii_hex)
   22
   >>> rs = unicodetools.codepoints_to_codepointranges(ascii_hex)
   >>> rs
   [unicodetools.collections.CodePointRange(0x0030, 0x0039),
    unicodetools.collections.CodePointRange(0x0041, 0x0046),
    unicodetools.collections.CodePointRange(0x0061, 0x0066)]
   >>> '|'.join(r.as_generic_re_pattern() for r in rs)
   '[0-9]|[A-F]|[a-f]'


``CodePointMultiRange`` class
-----------------------------

The ``CodePointMultiRange`` class serves as a wrapper around a collection
of ``CodePointRange`` instances.  Initilization with the keyword argument
``codepoints`` accepts a sequence of code points.  Initialization with
keyword ``codepointranges`` accepts a sequence of ``CodePointRange``
instances, such as might be returned by ``codepoints_to_codepointranges()``.
Note that the keyword must be provided explicitly.

The ``CodePointMultiRange`` class has the same methods for generating
regular expressions as the ``CodePointRange`` class.  Regular expression
patterns created with ``CodePointMultiRange`` automatically merge character
sets ``[<chars>]`` whenever possible, so the produced patterns are concise.

.. code::

   >>> import unicodetools
   >>> ascii_hex = []
   >>> for cp in range(0, 0x10FFFF+1):
       if cp in unicodetools.ucd.proplist:
           if 'ASCII_Hex_Digit' in unicodetools.ucd.proplist[cp]:
               ascii_hex.append(cp)

   >>> mr = unicodetools.CodePointMultiRange(codepoints=ascii_hex)
   >>> mr.as_generic_re_pattern()
   '[0-9A-Fa-f]'
