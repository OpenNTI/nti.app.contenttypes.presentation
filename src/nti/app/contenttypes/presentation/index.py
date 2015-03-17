#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

import zope.intid

from zope import component
from zope import interface

from zc.catalog.interfaces import ISetIndex
from zc.catalog.interfaces import IValueIndex

import BTrees

from nti.zope_catalog.index import SetIndex as RawSetIndex
from nti.zope_catalog.index import ValueIndex as RawValueIndex

PARENT_INDEX_NAME = '++etc++contenttypes.presentation-parent-index'
INTERFACE_INDEX_NAME = '++etc++contenttypes.presentation-interface-index'

family = BTrees.family64

class ParentIndex(RawSetIndex):
	
	def index_doc(self, doc_id, value):
		if isinstance(value, six.string_types):
			value = (value,)
		return super(ParentIndex, self).index_doc(doc_id, value)
	
class InterfaceIndex(RawValueIndex):
	
	def index_doc(self, doc_id, value):
		assert 	value is None or isinstance(value, six.string_types) or \
				issubclass(value, interface.Interface)
				
		if issubclass(value, interface.Interface):
			value = value.__name__
		return super(InterfaceIndex, self).index_doc(doc_id, value)
		
def install_indices(context):
	conn = context.connection
	root = conn.root()

	dataserver_folder = root['nti.dataserver']
	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(zope.intid.IIntIds)

	for name, factory, iface in ((PARENT_INDEX_NAME, ParentIndex, ISetIndex),
						  		 (INTERFACE_INDEX_NAME, InterfaceIndex, IValueIndex)):
		index = factory()
		index.__parent__ = dataserver_folder
		index.__name__ = name

		intids.register(index)
		lsm.registerUtility(index, provided=iface)

def index_item(docid, item_iface=None, parents=(), intids=None):
	intids = component.getUtility(zope.intid.IIntIds) if intids is None else None
	if docid is not None:
		index = component.getUtility(ISetIndex, name=PARENT_INDEX_NAME)
		index.index_doc(docid, parents)
		
		index = component.getUtility(IValueIndex, name=INTERFACE_INDEX_NAME)
		index.index_doc(docid, item_iface)

def unindex_item(docid):
	if docid is not None:
		for name, iface in ((PARENT_INDEX_NAME, ISetIndex),
						  	(INTERFACE_INDEX_NAME, IValueIndex)):
			index = component.getUtility(iface, name=name)
			index.unindex_doc(docid)

def search_by(item_iface=None, parents=()):
	if item_iface is not None:
		index = component.getUtility(IValueIndex, name=INTERFACE_INDEX_NAME)
		item_iface = getattr(item_iface, '__name__', item_iface)
		result_by_iface = index.apply({'any_of': (item_iface,)})
	else:
		result_by_iface = None

	if parents:
		parents = (parents,) if isinstance(parents, six.string_types) else parents
		index = component.getUtility(ISetIndex, name=PARENT_INDEX_NAME)
		result_by_parents = index.apply({'any_of': parents})
	else:
		result_by_parents = None

	if result_by_iface and result_by_parents:
		result = family.IF.intersection(result_by_parents, result_by_iface)
	elif result_by_iface:
		result = result_by_iface
	elif result_by_parents:
		result = result_by_parents
	else:
		result = family.IF.Set()
	return result
