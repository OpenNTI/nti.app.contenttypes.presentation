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

import zope.deferredimport
zope.deferredimport.initialize()

zope.deferredimport.deprecated(
	"Import from KeepSetIndex instead",
	KeepSetIndex='nti.contentlibrary.indexed_data.index:KeepSetIndex')

zope.deferredimport.deprecated(
	"Import from NamespaceIndex instead",
	NamespaceIndex='nti.contentlibrary.indexed_data.index:NamespaceIndex')

zope.deferredimport.deprecated(
	"Import from TypeIndex instead",
	TypeIndex='nti.contentlibrary.indexed_data.index:TypeIndex')

deprecated('PresentationAssetCatalog', 'Use lastest library index implementation')
class PresentationAssetCatalog(Persistent):

	def reset(self):
		pass

deprecated('PACatalogIndex', 'Use lastest library index implementation')
class PACatalogIndex(Persistent):
	pass
