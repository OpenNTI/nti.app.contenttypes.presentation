#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 22

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from zope.component.hooks import site as current_site

from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

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

def _valid_parent(item, intids):
	parent = item.__parent__
	doc_id = intids.queryId(parent) if parent is not None else None
	return parent is not None and doc_id is not None

def remove_leaks(current, intids, catalog, seen):
	site_name = current.__name__
	registry = current.getSiteManager()
	for ntiid, item in list(registry.getUtilitiesFor(IPresentationAsset)): # mutating
		if ntiid in seen:
			continue
		doc_id = intids.queryId(item)

		# registration for a removed asset
		if doc_id is None:
			logger.warn("Removing invalid registration %s from site %s", ntiid, site_name)
			remove_presentation_asset(item, registry, catalog, package=False)
			continue

		# invalid lesson overview
		if INTILessonOverview.providedBy(item) and not _valid_parent(item, intids):
			logger.warn("Removing invalid lesson overview %s from site %s",
						ntiid, site_name)
			remove_presentation_asset(item, registry, catalog, package=False)
			continue

		# invalid overview groups overview
		if INTICourseOverviewGroup.providedBy(item) and not _valid_parent(item, intids):
			logger.warn("Removing invalid course overview %s from site %s",
						ntiid, site_name)
			remove_presentation_asset(item, registry, catalog, package=False)
			continue
		
		# invalid media roll overview
		if INTIMediaRoll.providedBy(item) and not _valid_parent(item, intids):
			logger.warn("Removing invalid media roll %s from site %s",
						ntiid, site_name)
			remove_presentation_asset(item, registry, catalog)
			continue
		
		seen.add(ntiid)

def clean_containers(current, intids, seen):
	with current_site(current):
		catalog = component.queryUtility(ICourseCatalog)
		if catalog is None or catalog.isEmpty():
			return
		for entry in catalog.iterCatalogEntries():
			if entry.ntiid in seen:
				continue
			seen.add(entry.ntiid)
			course = ICourseInstance(entry)
			container = IPresentationAssetContainer(course)
			for ntiid, item in list(container.items()): # mutating
				doc_id = intids.queryId(item)
				if doc_id is None or not _valid_parent(item, intids):
					logger.warn("Removing %s from course container %s",
								ntiid, entry.ntiid)
					container.pop(ntiid, None)
		
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
		for current in get_all_host_sites():
			remove_leaks(current, intids, catalog, seen)

		seen = set()
		for current in get_all_host_sites():
			clean_containers(current, intids, seen)

	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 22 by removing leaks and clean course containers
	"""
	do_evolve(context, generation)
