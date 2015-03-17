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

from nti.zope_catalog.index import ValueIndex as RawValueIndex

from .interfaces import IParentIndex

PARENT_INDEX_NAME = '++etc++contenttypes.presentation-index'

class ParentIndex(RawValueIndex):
	
	def index_doc(self, doc_id, value):
		assert value is None or isinstance(value, six.string_types)
		return super(ParentIndex, self).index_doc(doc_id, value)
		
def install_parent_index(context):
	conn = context.connection
	root = conn.root()

	dataserver_folder = root['nti.dataserver']
	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(zope.intid.IIntIds)

	index = ParentIndex()
	index.__parent__ = dataserver_folder
	index.__name__ = PARENT_INDEX_NAME

	intids.register(index)
	lsm.registerUtility(index, provided=IParentIndex)

	return index
