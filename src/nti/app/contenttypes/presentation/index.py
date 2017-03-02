#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.deprecation import deprecated

from persistent import Persistent


deprecated('KeepSetIndex', 'Use lastest library index implementation')
class KeepSetIndex(Persistent):
    pass


deprecated('NamespaceIndex', 'Use lastest library index implementation')
class NamespaceIndex(Persistent):
    pass


deprecated('TypeIndex', 'Use lastest library index implementation')
class TypeIndex(Persistent):
    pass


deprecated('PACatalogIndex', 'Use lastest library index implementation')
class PACatalogIndex(Persistent):
    pass


deprecated('PresentationAssetCatalog', 'Use lastest library index implementation')
class PresentationAssetCatalog(Persistent):
    pass
