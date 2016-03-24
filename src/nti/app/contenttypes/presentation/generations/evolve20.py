#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 20

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import site as current_site

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_packages
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

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

def _course_asset_interfaces():
	result = []
	for iface in ALL_PRESENTATION_ASSETS_INTERFACES:
		if iface not in PACKAGE_CONTAINER_INTERFACES:
			result.append(iface)
	return result

def _add_2_packages(context, item):
	result = []
	for package in get_course_packages(context):
		container = IPresentationAssetContainer(package)
		container[item.ntiid] = item
		result.append(package.ntiid)
	return result

def _add_2_course(context, item):
	course = ICourseInstance(context, None)
	if course is not None:
		container = IPresentationAssetContainer(course, None)
		container[item.ntiid] = item

def _add_2_courses(context, item):
	_add_2_course(context, item)
	for subinstance in get_course_subinstances(context):
		_add_2_course(subinstance, item)

def _add_2_container(context, item, packages=False):
	result = []
	_add_2_courses(context, item)
	if packages:
		result.extend(_add_2_packages(context, item))
	entry = ICourseCatalogEntry(context, None)
	if entry is not None:
		result.append(entry.ntiid)
	return result

def _process_nodes(registry, seen):
	for ntiid, node in registry.getUtilitiesFor(ICourseOutlineNode):
		if ntiid in seen:
			continue
		seen.add(ntiid)
		name = node.LessonOverviewNTIID or u''
		lesson = registry.queryUtility(INTILessonOverview, name=name)
		if lesson is None or lesson.__parent__ is not None:
			continue

		lesson.__parent__ = node
		course = find_interface(node, ICourseInstance, strict=False)
		if course is None:
			continue

		logger.info("Reparenting %s", name)

		_add_2_container(course, lesson, packages=False)
		for group in lesson:
			group.__parent__ = lesson
			_add_2_container(course, group, packages=False)
			for item in group:
				provided = iface_of_asset(item)
				if not provided in PACKAGE_CONTAINER_INTERFACES:
					item.__parent__ = group
					_add_2_container(course, item, packages=False)
				else:
					_add_2_container(course, item, packages=True)
					if item.__parent__ is None:
						# Parent is first content package available.
						packages = get_course_packages(course)
						package = packages[0] if packages else None
						if package is not None:
							item.__parent__ = package

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
				_process_nodes(registry, seen)

	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 20 by fixing authored lesson lineage.
	"""
	do_evolve(context, generation)
