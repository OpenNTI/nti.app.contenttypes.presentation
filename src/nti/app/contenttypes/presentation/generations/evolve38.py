#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 38

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.externalization.interfaces import StandardExternalFields

from nti.site.hostpolicy import get_all_host_sites

from nti.traversal.traversal import find_interface

NTIID = StandardExternalFields.NTIID

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

def _fix_media_refs(current_site, seen):
	result = 0
	registry = current_site.getSiteManager()
	for interface in (INTIVideo, INTIAudio):
		for name, item in list(registry.getUtilitiesFor(interface)):
			if name in seen:
				continue
			seen.add(name)
			for field in ('sources', 'transcripts'):
				for part in getattr(item, field, None) or ():
					part.__parent__ = item
					part.__dict__.pop(NTIID, None) # remove ntiid
					part.__dict__.pop(NTIID.lower(), None) # remove ntiid
					result += 1
	return result

def _fix_containers_refs(current_site, seen, catalog):
	result = 0
	registry = current_site.getSiteManager()
	for name, item in list(registry.getUtilitiesFor(IAssetRef)):
		if name in seen:
			continue
		seen.add(name)
		concrete = IConcreteAsset(item, item)
		if concrete is item:
			continue
		extended = set()
		group = find_interface(item, INTICourseOverviewGroup, strict=False)
		lesson = find_interface(group, INTILessonOverview, strict=False)
		if group is not None:
			extended.add(group.ntiid)
		if lesson is not None:
			extended.add(lesson.ntiid)
		course = find_interface(lesson, ICourseInstance , strict=False)
		if ILegacyCourseInstance.providedBy(course) or course is None:
			continue
		entry = ICourseCatalogEntry(course)
		extended.add(entry.ntiid)
		extended.discard(None)
		catalog.update_containers(concrete, extended)
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

		result = 0
		seen = set()
		logger.info('Evolution %s started.', generation)
		
		catalog = get_library_catalog()
		for current_site in get_all_host_sites():
			with site(current_site):
				result += _fix_media_refs(current_site, seen)
				result += _fix_containers_refs(current_site, seen, catalog)

		logger.info('Evolution %s done. %s item(s) processed',
					generation, result)

def evolve(context):
	"""
	Evolve to 38 by setting lineage to transcripts and sources
	"""
	do_evolve(context, generation)
