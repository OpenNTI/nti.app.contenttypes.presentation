#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 19

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import site as current_site

from nti.app.contenttypes.presentation.utils.common import yield_sync_courses

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites
from nti.site.site import get_component_hierarchy_names

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

def _process_course(course, ntiid):
	catalog = get_library_catalog()
	registry = component.getSiteManager()
	sites = get_component_hierarchy_names()
	container = IPresentationAssetContainer(course)
	for item in catalog.search_objects(sites=sites,
									   container_ntiids=ntiid,
									   container_all_of=False):
		provided = iface_of_asset(item)
		if 		provided not in PACKAGE_CONTAINER_INTERFACES \
			and registry.queryUtility(provided, name=item.ntiid) != None:
			container[ntiid] = item
	
def _process_courses(registry, seen):
	for course in yield_sync_courses():
		ntiid = ICourseCatalogEntry(course).ntiid
		if ntiid not in seen:
			seen.add(ntiid)
			_process_course(course, ntiid)

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = ds_folder
	component.provideUtility(mock_ds, IDataserver)

	seen = set()
	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		for site in get_all_host_sites():
			with current_site(site):
				registry = component.getSiteManager()
				_process_course(registry, seen)

	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 19 by resetting items in course containers
	"""
	do_evolve(context, generation)
