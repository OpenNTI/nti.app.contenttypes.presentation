#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 24

from itertools import chain

from zope import component
from zope import interface

from zope.component.hooks import site, setHooks

from zope.intid.interfaces import IIntIds

from nti.app.contenttypes.presentation.utils import component_site

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.traversal import find_nearest_site

from nti.intid.common import addIntId

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import get_all_host_sites

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

def _get_content_package( course ):
	try:
		packages = course.ContentPackageBundle.ContentPackages
	except AttributeError:
		try:
			packages = (course.legacy_content_package,)
		except AttributeError:
			try:
				packages = course.ContentPackages
			except AttributeError:
				packages = ()
	return packages[0] if packages else None

def _update_asset_lineage( current_site, item, lesson, package ):
	old_unit = find_interface( item, IContentUnit, strict=False )
	new_unit = None
	if old_unit is not None:
		# First, try a new unit with the same ntiid.
		new_unit = find_object_with_ntiid( old_unit.ntiid )
	else:
		# No unit, use the unit the lesson points to.
		lesson_node = find_interface( lesson, ICourseOutlineContentNode, strict=False )
		if lesson_node is not None:
			new_unit = find_object_with_ntiid( lesson_node.ContentNTIID )

	if new_unit is None:
		# None of the above, use our course content package.
		new_unit = package

	if new_unit is None:
		logger.warn( '[%s] No content unit root found for (%s)',
					 current_site.__name__, item.ntiid )
		return False

	assert new_unit is not old_unit
	container = IPresentationAssetContainer( new_unit )
	container[item.ntiid] = item
	item.__parent__ = new_unit
	logger.info( '[%s] Updated lineage (%s) (parent=%s)',
				 current_site.__name__, item.ntiid, new_unit.ntiid )
	return True

def _get_site_name( group ):
	provided = iface_of_asset(group)
	return component_site(group,
						  provided=provided,
						  name=group.ntiid)

def _do_index( item, containers, namespace, site_name, current_site, intids, catalog ):
	# Validate intid before indexing
	item_intid = intids.queryId(item)
	if item_intid is None:
		logger.info( '[%s] Item without intid (%s)',
					 current_site.__name__, item.ntiid )
		addIntId( item )
	catalog.index(item,
				  container_ntiids=containers,
				  namespace=namespace,
				  sites=site_name)

def _index_asset( current_site, item, course, package, lesson, group, site_name, intids ):
	catalog = get_library_catalog()
	entry = ICourseCatalogEntry( course, None )
	if package is None:
		logger.warn( '[%s] No package found for item (%s)',
					 current_site.__name__, item.ntiid )
	if entry is None:
		logger.warn( '[%s] No catalog entry found for item (%s)',
					 current_site.__name__, item.ntiid )
	namespace = package.ntiid if package else entry and entry.ntiid
	containers = [lesson.ntiid, group.ntiid]
	if package is not None:
		containers.append( package.ntiid )
	if entry is not None:
		containers.append( entry.ntiid )

	_do_index( item, containers, namespace, site_name, current_site, intids, catalog )

	if INTISlideDeck.providedBy( item ):
		containers.append( item.ntiid )
		for slide_item in chain(item.Slides or (), item.Videos or ()):
			_do_index( slide_item, containers, namespace, site_name, current_site, intids, catalog )
	return True

def _update_assets( seen, current_site, intids ):
	result = index_count = 0
	library = component.queryUtility(IContentPackageLibrary)
	if library is None:
		return result

	# Loop through all assets in all groups.
	for name, group in list(component.getUtilitiesFor(INTICourseOverviewGroup)):
		if name in seen:
			continue
		seen.add(name)
		if not group:
			continue
		lesson = find_interface( group, INTILessonOverview, strict=False )
		course = ICourseInstance( group, None )
		package = _get_content_package( course ) if course else None
		site_name = _get_site_name( group )
		for item in group:
			if INTIMediaRef.providedBy( item ):
				ref_item = item
				item = INTIMedia( item, None )
				if item is None:
					# ~5 of these in alpha
					logger.warn( '[%s] No media object found for ref (%s)',
							 	 current_site.__name__, ref_item.ntiid )
					continue
			if not IPackagePresentationAsset.providedBy( item ):
				continue
			try:
				# Easiest way is to check if our lineage reaches a site folder.
				find_nearest_site( item )
			except TypeError:
				if _update_asset_lineage( current_site, item, lesson, package ):
					result += 1
			index_count += 1
			# Now update index
			if _index_asset( current_site, item, course, package, lesson, group, site_name, intids ):
				index_count += 1

	logger.info('[%s] Lineage fixed (%s) and indexed (%s)',
				 current_site.__name__,
				 result, index_count )
	return result

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
		# Do not need to do this in global site.
		for current_site in get_all_host_sites():
			with site(current_site):
				_update_assets( seen, current_site, intids )
		logger.info('Dataserver evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to 24 by fixing lineage for authored assets, putting them in
	the correct container, and making sure everything has an intid and
	is indexed correctly.
	"""
	do_evolve(context, generation)
