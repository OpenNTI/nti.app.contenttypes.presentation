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

from nti.common.property import alias
from nti.common.time import bit64_int_to_time
from nti.common.time import time_to_64bit_int

from nti.zope_catalog.catalog import ResultSet
from nti.zope_catalog.index import SetIndex as RawSetIndex
from nti.zope_catalog.index import ValueIndex as RawValueIndex

from .interfaces import IPresentationAssetsIndex

from . import CATALOG_INDEX_NAME
		
def install_catalog(context):
	conn = context.connection
	root = conn.root()

	dataserver_folder = root['nti.dataserver']
	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(IIntIds)

	index = PresentationAssetCatalog()
	index.__parent__ = dataserver_folder
	index.__name__ = CATALOG_INDEX_NAME

	intids.register(index)
	lsm.registerUtility(index, provided=IPresentationAssetsIndex,
						name=CATALOG_INDEX_NAME)

class KeepSetIndex(RawSetIndex):
	"""
	An set index that keeps the old values
	"""

	def index_doc(self, doc_id, value):
		value = (value,) if isinstance(value, six.string_types) else value
		value = {v for v in value if v is not None}
		old = self.documents_to_values.get(doc_id)
		value.update(old or ())
		result = super(KeepSetIndex, self).index_doc(doc_id, value)
		return result
		
class NamespaceIndex(RawValueIndex):
	pass
		
class TypeIndex(RawValueIndex):
	pass

class PresentationAssetCatalog(Persistent):
	
	family = BTrees.family64
	
	_container_index = alias('_entry_index')
	
	def __init__(self):
		self.reset()
	
	def reset(self):
		self._last_modified = self.family.OI.BTree()
		## track the object type (interface name)
		self._type_index = TypeIndex(family=self.family)
		## track the containers the object belongs to
		self._entry_index = KeepSetIndex(family=self.family)
		## track the source/file name an object was read from
		self._namespace_index = NamespaceIndex(family=self.family)
			
	def _doc_id(self, item, intids=None):
		intids = component.queryUtility(IIntIds) if intids is None else intids
		if not isinstance(item, int):
			doc_id = intids.queryId(item) if intids is not None else None
		else:
			doc_id = item
		return doc_id
	
	def get_last_modified(self, namespace):
		try:
			return bit64_int_to_time(self._last_modified[namespace])
		except KeyError:
			return 0

	def set_last_modified(self, namespace, t=None):
		assert isinstance(namespace, six.string_types)
		t = time.time() if t is None else t
		self._last_modified[namespace] = time_to_64bit_int(t)
	
	def remove_last_modified(self, namespace):
		try:
			del self._last_modified[namespace]
		except KeyError:
			pass
		
	def get_containers(self, item, intids=None):
		intids = component.queryUtility(IIntIds) if intids is None else intids
		doc_id = self._doc_id(item, intids)
		if doc_id is None:
			result = ()
		else:
			result = self._container_index.documents_to_values.get(doc_id)
			result = set(result or ())
		return result

	def get_references(self, container=None, kind=None, namespace=None):
		result = None
		for index, value, query in ( (self._type_index, kind, 'any_of'),
							  		 (self._container_index, container, 'all_of'), 
							  		 (self._namespace_index, namespace, 'any_of')):
			if value is not None:
				value = getattr(value, '__name__', value)
				ids = index.apply({query: (value,)}) or self.family.IF.LFSet()
				if result is None:
					result = ids
				else:
					result = self.family.IF.intersection(result, ids)
		return result or ()

	def search_objects(self, container=None, kind=None, namespace=None, intids=None):
		intids = component.queryUtility(IIntIds) if intids is None else intids
		if intids is not None:
			refs = self.get_references(container, kind, namespace)
			result = ResultSet(refs, intids)
		else:
			result = ()
		return result

	def index(self, item, container=None, kind=None, namespace=None, intids=None):
		doc_id = self._doc_id(item, intids)
		if doc_id is None:
			return False

		for index, value in ( (self._type_index, kind),
							  (self._container_index, container), 
							  (self._namespace_index, namespace)):
			if value is not None:
				value = getattr(value, '__name__', value)
				index.index_doc(doc_id, value)
		return True
		
	def unindex(self, item, intids=None):
		doc_id = self._doc_id(item, intids)
		if doc_id is None:
			return False
		for index in (self._container_index, self._type_index, self._namespace_index):
			index.unindex_doc(doc_id)
		return True
