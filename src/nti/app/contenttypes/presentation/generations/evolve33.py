#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 33

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from ZODB.interfaces import IConnection

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.intid.common import addIntId

from nti.site.hostpolicy import get_all_host_sites

from nti.site.utils import registerUtility

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

def _fix_media(current_site, seen):
	registry = current_site.getSiteManager()
	for ntiid, media in list(registry.getUtilitiesFor(INTIMedia)):
		if ntiid in seen:
			continue
		seen.add(ntiid)
		for name in ('transcripts', 'sources'):
			things = getattr(media, name, None)
			for thing in things or ():
				thing.__parent__ = media
		continue
		
def _replace_with_refs(current_site, catalog, intids, seen):
	result = 0
	registry = current_site.getSiteManager()
	connection = IConnection(registry, None)
	for name, group in list(registry.getUtilitiesFor(INTICourseOverviewGroup)):
		if name in seen:
			continue
		seen.add(name)

		# don't process legacy courses
		lesson = group.__parent__
		course = find_interface(lesson, ICourseInstance, strict=False)
		if ILegacyCourseInstance.providedBy(course) or course is None:
			continue
		entry = ICourseCatalogEntry(course)

		namespace = entry.ntiid
		course_container = IPresentationAssetContainer(course)
		group_containers = set(catalog.get_containers(group) or ())

		# loop through items
		for idx, item in enumerate(group or ()): # mutating
			containers = {group.ntiid, lesson.ntiid}
			containers.update(group_containers)

			if 		INTIRelatedWorkRefPointer.providedBy(item) \
				or	INTITimelineRef.providedBy(item) \
				or	INTIVideoRef.providedBy(item):
				concrete = IConcreteAsset(item, None)
				if concrete is not None:
					package = find_interface(concrete, IContentPackage, strict=False)
					if package is not None:
						containers.add(package.ntiid)
					catalog.index(concrete,
							  	  container_ntiids=containers)
				continue

			if not INTIRelatedWorkRef.providedBy(item):
				continue
			containers = {group.ntiid, lesson.ntiid}
			containers.update(group_containers)
			
			asset_ref = INTIRelatedWorkRefPointer(item)
			connection.add(asset_ref)
			ntiid = asset_ref.ntiid
			addIntId(asset_ref)

			# register new item ref
			registerUtility(registry, 
							asset_ref,
							provided=INTIRelatedWorkRefPointer, 
							name=ntiid)
			
			# set lineage
			asset_ref.__parent__ = group
			group[idx] = asset_ref # replace
			
			# set in course asset container
			course_container.pop(item.ntiid, None)
			course_container[ntiid] = asset_ref
			
			# index
			containers.discard(None)
			catalog.index(asset_ref,
					  	  namespace=namespace,
					  	  sites=current_site.__name__,
					  	  container_ntiids=containers)
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

	with site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = dataserver_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)

		library = component.queryUtility(IContentPackageLibrary)
		if library is not None:
			library.syncContentPackages()
			
		result = 0
		seen = set()
		catalog = get_library_catalog()

		logger.info('Evolution %s started.', generation)
		
		for current_site in get_all_host_sites():
			with site(current_site):
				_fix_media(current_site, seen)
				result += _replace_with_refs(current_site, catalog, intids, seen)

		logger.info('Evolution %s done. %s item(s) fixed',
					generation, result)

def evolve(context):
	"""
	Evolve to 33 by creating related work ref pointers
	"""
	do_evolve(context, generation)
