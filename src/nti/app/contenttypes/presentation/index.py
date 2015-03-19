#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import time

from zope.intid import IIntIds

from zope import component

import BTrees

from persistent import Persistent

from nti.zope_catalog.catalog import ResultSet
from nti.zope_catalog.index import SetIndex as RawSetIndex

from .interfaces import IPresentationAssetsIndex

PACATALOG_INDEX_NAME = '++etc++contenttypes.presentation-index'
		
def install_indices(context):
	conn = context.connection
	root = conn.root()

	dataserver_folder = root['nti.dataserver']
	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(IIntIds)

	index = PACatalogIndex()
	index.__parent__ = dataserver_folder
	index.__name__ = PACATALOG_INDEX_NAME

	intids.register(index)
	lsm.registerUtility(index, provided=IPresentationAssetsIndex,
						name=PACATALOG_INDEX_NAME)

def get_index():
	result = component.queryUtility(IPresentationAssetsIndex, name=PACATALOG_INDEX_NAME)
	return result
get_catalog = get_index

class PACatalogIndex(Persistent):
	
	family = BTrees.family64
	
	def __init__(self):
		self.reset()
	
	def reset(self):
		self._last_modified = self.family.OI.BTree()
		self._references = RawSetIndex(family=self.family)
		
	def get_last_modified(self, key):
		try:
			return self._last_modified[key]
		except KeyError:
			return 0

	def set_last_modified(self, key, t=None):
		assert isinstance(key, six.string_types)
		t = time.time() if t is None else t
		self._last_modified[key] = int(t)
	
	def remove_last_modified(self, key):
		try:
			del self._last_modified[key]
		except KeyError:
			pass
		
	def get_references(self, *keys):
		keys = map(lambda x: getattr(x, '__name__', x), keys)
		result = self._references.apply({'all_of': keys})
		return result

	def search_objects(self, keys=(), intids=None):
		intids = component.queryUtility(IIntIds) if intids is None else intids
		if intids is not None:
			refs = self.get_references(*keys)
			result = ResultSet(refs, intids)
		else:
			result = ()
		return result

	def index(self, item, values=(), intids=None):
		intids = component.queryUtility(IIntIds) if intids is None else intids
		if not isinstance(item, int):
			item = intids.queryId(item) if intids is not None else None
		if item is None:
			return False
		## make sure we keep the old values when updating index
		values = set(map(lambda x: getattr(x, '__name__', x), values))
		old = self._references.documents_to_values.get(item)
		values.update(old or ())
		self._references.index_doc(item, values)
		return True
		
	def unindex(self, value, intids=None):
		intids = component.queryUtility(IIntIds) if intids is None else intids
		if not isinstance(value, int):
			value = intids.queryId(value) if intids is not None else None
		if value is not None:
			self._references.unindex_doc(value)
