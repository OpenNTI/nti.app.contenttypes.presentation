#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 9

import functools

from zope import component
from zope import interface

from zope.component.hooks import site, setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.indexed_data import CATALOG_INDEX_NAME
from nti.contentlibrary.indexed_data.interfaces import IContainedObjectCatalog

from nti.contenttypes.courses.interfaces import ICourseCatalog 
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import run_job_in_all_host_sites

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

def _reindex_items(catalog, intids):
	catalog = component.queryUtility( ICourseCatalog )
	if catalog is None:
		return

	for entry in catalog.iterCatalogEntries():
		course = ICourseInstance(entry, None)
		if course is None:
			continue
		container = IPresentationAssetContainer(course, None)
		if container is None:
			continue
		ntiid = entry.ntiid
		assets = catalog.search_objects(container_ntiids=ntiid, intids=intids)
		for asset in assets:
			container[asset.ntiid] = asset

def do_evolve(context):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = dataserver_folder
	component.provideUtility(mock_ds, IDataserver)
	
	with site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = dataserver_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		catalog = lsm.getUtility(IContainedObjectCatalog, name=CATALOG_INDEX_NAME)

		run_job_in_all_host_sites(functools.partial(_reindex_items, catalog, intids))
		logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to gen 9 by registering assets with course
	"""
	do_evolve(context)
