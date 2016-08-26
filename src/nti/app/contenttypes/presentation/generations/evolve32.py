#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 32

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentUnit 
from nti.contentlibrary.interfaces import IContentPackage 
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.intid.common import removeIntId

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import get_all_host_sites

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

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

def _fix_refs(current_site, catalog, intids, seen):
	result = 0
	registry = current_site.getSiteManager()
	for name, group in list(registry.getUtilitiesFor(INTICourseOverviewGroup)):
		if name in seen:
			continue
		seen.add(name)

		# don't process legacy courses
		lesson = group.__parent__
		course = find_interface(lesson, ICourseInstance, strict=False)
		if ILegacyCourseInstance.providedBy(course):
			continue
		
		course_packages = tuple(get_course_packages(course) or ())

		#  loop through items
		for item in group or ():
			name = item.ntiid
			if not name:
				continue

			if INTIRelatedWorkRef.providedBy(item) or INTITimeline.providedBy(item):
				namespace = None
				provided = iface_of_asset(item)
				containers = {group.ntiid, lesson.ntiid}
				registered = registry.queryUtility(provided, name=name)
				if registered.__parent__ is None or registered is not item:
					logger.warn("Fixing %s", name)
					parent = registered.__parent__
					package = find_interface(registered, IContentPackage, strict=False)
					
					doc_id = intids.queryId(registered)
					if doc_id is not None:
						namespace = catalog.get_namespace(doc_id) 
						containers.update(catalog.get_containers(doc_id) or ())
					else:
						namespace = None
							
					if registered is not item:
						# remove registered / lesson wins
						if doc_id is not None:
							catalog.unindex(doc_id)
							removeIntId(registered)
						unregisterUtility(registry, provided=provided, name=name)
						# register new item and set proper lineage
						registerUtility(registry, item, provided=provided, name=name)

					# remove from and replace in asset containers
					found_in_units = False
					for container_ntiid in containers:
						unit = find_object_with_ntiid(container_ntiid)
						if IContentUnit.providedBy(unit):
							found_in_units = True
							container = IPresentationAssetContainer(unit, None)
							if container is not None:
								container.pop(name, None)
								container[name] = item
								containers.add(unit.ntiid)
								if parent is None and package is None:
									package = find_interface(unit, 
															 IContentPackage, 
															 strict=False)

					if package is None and course_packages:
						package = course_packages[0]

					# give a default asset container
					if not found_in_units and package is not None:
						container = IPresentationAssetContainer(package)
						container.pop(name, None)
						container[name] = item
						containers.add(package.ntiid)

					if parent is not None:
						item.__parent__ = parent

					# find proper namespace
					if package is not None:
						namespace = package.ntiid
						if 		item.__parent__ is None or \
							not IContentPackage.providedBy(item.__parent__):
							item.__parent__ = package

					# index
					containers.discard(None)
					catalog.index(item,
							  	  namespace=namespace,
							  	  sites=current_site.__name__,
							  	  container_ntiids=containers)

					# ground
					if registered is not item:
						registered.__parent__ = None
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

		for current_site in get_all_host_sites():
			with site(current_site):
				result += _fix_refs(current_site, catalog, intids, seen)

		logger.info('Dataserver evolution %s done. %s item(s) fixed',
					generation, result)

def evolve(context):
	"""
	Evolve to 32 by fixing registration of docket items
	"""
	do_evolve(context, generation)
