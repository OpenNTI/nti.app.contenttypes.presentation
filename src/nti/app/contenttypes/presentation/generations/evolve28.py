#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 28

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IItemAssetContainer
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.intid.common import addIntId

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import get_all_host_sites

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

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

def _get_content_package(course):
	packages = get_course_packages(course)
	return packages[0] if packages else None

def _get_site_name(group):
	folder = find_interface(group, IHostPolicyFolder, strict=False)
	return folder.__name__ if folder is not None else None

def _do_index(item, containers, namespace, site_name, current_site, intids, catalog):
	# Validate intid before indexing
	item_intid = intids.queryId(item)
	if item_intid is None:
		logger.info('[%s] Item without intid (%s)',
					 current_site.__name__, item.ntiid)
		addIntId(item)
	catalog.index(item,
				  container_ntiids=containers,
				  namespace=namespace,
				  sites=site_name)

def _index_asset(current_site, item, course, lesson, group, site_name, intids):
	"""
	Index our item with course/lesson/group (parent asset if needed).
	"""
	catalog = get_library_catalog()
	entry = ICourseCatalogEntry(course, None)
	if entry is None:
		# XXX: Some items do not have course because the lesson
		# does not have lineage (and is not found when traversing
		# the outline...orphaned?).
		logger.warn('[%s] No catalog entry found for item (%s)',
					 current_site.__name__, item.ntiid)
	containers = [lesson.ntiid, group.ntiid]
	if entry is not None:
		containers.append(entry.ntiid)
	namespace = lesson.ntiid

	_do_index(item, containers, namespace, site_name, current_site, intids, catalog)

	if IItemAssetContainer.providedBy(item):
		containers.append(item.ntiid)
		for child in item.Items:
			_do_index(child, containers, namespace, site_name, current_site, intids, catalog)
	return True

def _update_assets(seen, current_site, intids):
	lineage_count = index_count = 0
	library = component.queryUtility(IContentPackageLibrary)
	if library is None:
		return lineage_count

	# Loop through all assets in all groups.
	for name, group in list(component.getUtilitiesFor(INTICourseOverviewGroup)):
		if name in seen:
			continue
		seen.add(name)
		if not group:
			continue
		lesson = find_interface(group, INTILessonOverview, strict=False)
		course = ICourseInstance(group, None)
		site_name = _get_site_name(group) or current_site.__name__
		for item in group:
			index_count += 1
			# Make sure our parent is our group.
			if IGroupOverViewable.providedBy(item):
				lineage_count += 1
				item.__parent__ = group
			# Now update index
			if _index_asset(current_site, item, course, lesson, group, site_name, intids):
				index_count += 1

	logger.info('[%s] Lineage fixed (%s) and index updated (%s)',
				 current_site.__name__,
				 lineage_count, index_count)
	return lineage_count

def _update_node_lineage(seen_courses, current_site):
	catalog = component.queryUtility(ICourseCatalog)
	if catalog is None or catalog.isEmpty():
		return
	def _recur( node, parent ):
		# Set lineage recursively, including lessons.
		count = 1
		node.__parent__ = parent
		lesson_ntiid = getattr( node, 'LessonOverviewNTIID', '' )
		lesson = find_object_with_ntiid( lesson_ntiid ) if lesson_ntiid else None
		if lesson_ntiid and lesson is None:
			logger.info( '[%s] Lesson not found (%s)',
						 current_site.__name__, lesson_ntiid )
		if lesson is not None:
			count += 1
			lesson.__parent__ = node
		for child in node.values():
			count += _recur( child, node )
		return count

	lineage_count = 0
	for entry in catalog.iterCatalogEntries():
		if entry.ntiid in seen_courses:
			continue
		seen_courses.add(entry.ntiid)
		course = ICourseInstance(entry, None)
		if course is None or ILegacyCourseInstance.providedBy( course ):
			continue
		lineage_count += _recur( course.Outline, course )
	logger.info( '[%s] Updating lineage for %s objects',
				 current_site.__name__, lineage_count )

def do_evolve(context, generation=generation):
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

		# Load library
		library = component.queryUtility(IContentPackageLibrary)
		if library is not None:
			library.syncContentPackages()

		lsm = dataserver_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		seen = set()
		seen_courses = set()
		# Do not need to do this in global site.
		for current_site in get_all_host_sites():
			with site(current_site):
				_update_node_lineage( seen_courses, current_site )
				_update_assets(seen, current_site, intids)
		logger.info('Dataserver evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to 28 by making sure node lineage is correct, fixing container indexes
	for assets, and making sure ref parents are overview groups.
	"""
	do_evolve(context, generation)
