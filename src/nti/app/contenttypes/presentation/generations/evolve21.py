#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 21

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from zope.component.hooks import site as current_site

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.intid.common import removeIntId

from nti.site.hostpolicy import get_all_host_sites

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

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

def _process_items(current, sites, intids, catalog, seen):
	# capture hierarchy
	site_name = current.__name__
	site_names = get_component_hierarchy_names(current)
	
	site_index = catalog.site_index
	registry = current.getSiteManager()
	for ntiid, item in list(registry.getUtilitiesFor(IPresentationAsset)):
		provided = iface_of_asset(item)
		doc_id = intids.queryId(item)

		# registration for a removed asset
		if doc_id is None:
			logger.warn("Removing invalid registration %s from site %s",
						ntiid, site_name)
			unregisterUtility(registry, provided=provided, name=ntiid)
			continue

		# invalid lesson overview
		if INTILessonOverview.providedBy(item) and item.__parent__ is None:
			logger.warn("Removing invalid lesson overview %s from site %s",
						ntiid, site_name)
			removeIntId(item)
			catalog.unindex(doc_id)
			unregisterUtility(registry, provided=provided, name=ntiid)
			continue

		# registration not in base site
		if ntiid not in seen and len(site_names) > 1:
			site_name = site_names[-1]
			logger.warn("Moving %s to base site %s", ntiid, site_name)
			unregisterUtility(registry, provided=provided, name=ntiid)
			# new registry
			registry = sites[site_name].getSiteManager()
			registerUtility(registry, item, provided, ntiid)
			
		# make sure we index
		if 		site_name != current.__name__ \
			or	site_index.documents_to_values.get(doc_id) in (None, u'dataserver2'):
			logger.info("Indexing %s to site %s", ntiid, site_name)
			site_index.index_doc(doc_id, sites[site_name]) # pass host policy folder
			
		seen.add(ntiid)

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = ds_folder
	component.provideUtility(mock_ds, IDataserver)

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = ds_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		
		seen = set()
		catalog = get_library_catalog()
		
		sites = ds_folder['++etc++hostsites']
		for current in get_all_host_sites():
			_process_items(current, sites, intids, catalog, seen)

	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 21 by indexing site name in library catalog for assets
	"""
	do_evolve(context, generation)
