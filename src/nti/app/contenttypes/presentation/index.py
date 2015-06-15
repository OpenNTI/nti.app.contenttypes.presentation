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

import BTrees

from persistent import Persistent

from nti.common.time import bit64_int_to_time
from nti.common.time import time_to_64bit_int

from nti.contentlibrary.indexed_data import get_catalog

from .interfaces import IPresentationAssetsIndex

from . import CATALOG_INDEX_NAME

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

class PresentationAssetCatalog(Persistent):

	family = BTrees.family64

	def __init__(self):
		self.reset()

	def reset(self):
		self._last_modified = self.family.OI.BTree()

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
		result = get_catalog().get_containers(item, intids)
		return result

	def remove_containers(self, item, containers, intids=None):
		result = get_catalog().remove_containers(item, containers, intids)
		return result
	remove_container = remove_containers

	def remove_all_containers(self, item, intids=None):
		result = get_catalog().remove_all_containers(item, intids)
		return result

	def get_references(self, containers=None, provided=None, namespace=None, ntiid=None):
		result = get_catalog().get_references(containers, provided=provided, 
											  namespace=namespace, ntiid=ntiid)
		return result

	def search_objects(self, containers=None, provided=None, namespace=None,
					   ntiid=None, intids=None):
		result = get_catalog().search_objects(containers, provided=provided,
											  namespace=namespace, 
											  ntiid=ntiid, intids=intids)
		return result

	def index(self, item, containers=None, namespace=None, intids=None):
		result = get_catalog().index(item, containers, namespace, intids)
		return result

	def unindex(self, item, intids=None):
		result = get_catalog().unindex(item, intids)
		return result

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
