#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 31

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset
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

def _asset_container(context):
	container = IPresentationAssetContainer(context, None)
	return container if container is not None else dict()

def _add_2_package_container(course, item):
	packages = get_course_packages(course)
	if packages:
		item.__parent__ = packages[0]  # pick first
		container = _asset_container(packages[0])
		container[item.ntiid] = item
		return packages[0].ntiid
	return None

def _fix_refs(current_site, catalog, intids, seen):
	result = 0
	registry = current_site.getSiteManager()
	for name, group in list(registry.getUtilitiesFor(INTICourseOverviewGroup)):
		if name in seen:
			continue
		seen.add(name)

		course = find_interface(group, ICourseInstance, strict=False)
		for item in group or ():
			if not item.ntiid:
				delattr(item, 'ntiid')

			fixed = False
			doc_id = intids.queryId(item)
			if doc_id is None:
				addIntId(item)
				fixed = True

			provided = iface_of_asset(item)
			if registry.queryUtility(provided, name=item.ntiid) is None:
				fixed = True
				registerUtility(registry,
								item,
								provided,
								name=item.ntiid)
				result += 1

			if fixed:
				logger.info("[Re]registering %s", item.ntiid)
				containers = set(catalog.get_containers(group) or ())
				containers.update((group.ntiid, group.__parent__.ntiid))
				
				if IPackagePresentationAsset.providedBy(item):
					namespace = _add_2_package_container(course, item)
					containers.add(namespace)
					containers.discard(None)
				else:
					namespace = catalog.get_namespace(group)
					if item.__parent__ is None:
						item.__parent__ = group

				catalog.index(item,
							  namespace=namespace,
							  container_ntiids=containers,
							  sites=(current_site.__name__,),
							  intids=intids)
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
	Evolve to 31 by [re]registering missing assets
	"""
	do_evolve(context, generation)
