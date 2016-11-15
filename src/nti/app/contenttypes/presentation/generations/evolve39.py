#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 39

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.indexed_data.index import TargetIndex

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTIDocketAsset

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

@interface.implementer(IDataserver)
class MockDataserver(object):

	root = None

	def get_by_oid(self, oid, ignore_creator=False):
		resolver = component.queryUtility(IOIDResolver)
		if resolver is None:
			logger.warn("Using dataserver without a proper ISiteManager configuration.")
		else:
			return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
		return None

def _index_docket_assets(current_site, seen, index, intids):
	result = 0
	registry = current_site.getSiteManager()
	for provided in (INTIDocketAsset, IAssetRef):
		for _, item in list(registry.getUtilitiesFor(provided)):
			doc_id = intids.queryId(item)
			if doc_id is None or doc_id in seen:
				continue
			seen.add(doc_id)
			index.index_doc(doc_id, item)
			result += 1
	return result

def do_evolve(context, generation=generation):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = dataserver_folder
	component.provideUtility(mock_ds, IDataserver)

	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(IIntIds)
		
	with site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		result = 0
		seen = set()
		logger.info('Evolution %s started.', generation)

		catalog = get_library_catalog()
		if not hasattr(catalog, '_target_index'):
			catalog._target_index = TargetIndex(family=intids.family)
			for current_site in get_all_host_sites():
				with site(current_site):
					result += _index_docket_assets(current_site, seen, 
												   catalog._target_index,
												   intids)

		logger.info('Evolution %s done. %s item(s) processed',
					generation, result)

def evolve(context):
	"""
	Evolve to 39 by registering the target index in the library catalog
	"""
	do_evolve(context, generation)
