#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 24

import functools

from zope import component
from zope import interface

from zope.component.hooks import site, setHooks

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import run_job_in_all_host_sites

from nti.dataserver.traversal import find_nearest_site

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

def _update_asset_lineage( item, group ):
	old_unit = find_interface( item, IContentUnit, strict=False )
	new_unit = None
	if old_unit is not None:
		# First, try a new unit with the same ntiid.
		new_unit = find_object_with_ntiid( old_unit.ntiid )
	else:
		# No unit, use the unit the lesson points to.
		lesson = find_interface( item, INTILessonOverview, strict=False )
		if lesson is not None:
			new_unit = find_object_with_ntiid( lesson.ContentNTIID )

	if new_unit is None:
		# None of the above, use our course content package.
		course = ICourseInstance( group, None )
		if course is not None:
			new_unit = _get_content_package( course )

	if new_unit is None:
		logger.warn( 'No content unit root found for (%s)', item.ntiid )
		return False

	assert new_unit is not old_unit
	container = IPresentationAssetContainer( new_unit )
	container[item.ntiid] = item
	item.__parent__ = new_unit
	logger.info( 'Updated lineage (%s) (parent=%s)', item.ntiid, new_unit.ntiid )
	return True

def _update_assets(seen):
	result = 0
	library = component.queryUtility(IContentPackageLibrary)
	if library is None:
		return result

	# Loop through all assets in all groups.
	for name, group in list(component.getUtilitiesFor(INTICourseOverviewGroup)):
		if name in seen:
			continue
		seen.add(name)
		for item in group or ():
			if not IPackagePresentationAsset.providedBy( item ):
				continue
			try:
				# Easiest way is to check if our lineage reaches a site folder.
				find_nearest_site( item )
			except TypeError:
				if _update_asset_lineage( item, group ):
					result += 1

	logger.info('%s asset(s) lineage fixed (%s)', result, library)
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

		seen = set()
		# Do not need to do this in global site.
		run_job_in_all_host_sites(functools.partial(_update_assets, seen))
		logger.info('Dataserver evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to 24 by fixing lineage for authored assets, as well as putting them in
	correct container.
	"""
	do_evolve(context, generation)
