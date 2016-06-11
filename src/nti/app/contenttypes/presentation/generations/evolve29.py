#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 29

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from ZODB.interfaces import IConnection

from nti.app.contentlibrary.adapters import _PresentationAssetOOBTree
from nti.app.contentlibrary.adapters import _PresentationAssetContainer

from nti.app.contentlibrary.utils import yield_sync_content_packages

from nti.app.contenttypes.presentation.utils.common import yield_sync_courses

from nti.contentlibrary.interfaces import IGlobalContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

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

def _update_storage(context):
	try:
		connection = IConnection(context, None)
		old_container = context._presentation_asset_item_container
		if isinstance(old_container, _PresentationAssetContainer):
			new_container = _PresentationAssetOOBTree()
			new_container.__parent__ = context
			new_container.__name__ = old_container.__name__
			new_container.createdTime = old_container.createdTime
			new_container.lastModified = old_container.lastModified
			new_container.extend(old_container.values())
			context._presentation_asset_item_container = new_container
			if connection and IConnection(new_container, None) is None:
				connection.add(new_container)
			old_container.__parent__ = None  # ground
			old_container.clear()
	except AttributeError:
		pass

def _process_site(seen, current_site, intids):
	for course in yield_sync_courses():
		entry = ICourseCatalogEntry(course, None)
		if 		entry is None \
			or	entry.ntiid in seen \
			or	ILegacyCourseInstance.providedBy(course):
			continue
		seen.add(entry.ntiid)
		_update_storage(course)

	def _recur(unit):
		_update_storage(unit)
		for child in unit.children or ():
			_recur(child)

	for package in yield_sync_content_packages():
		if 		package.ntiid in seen \
			or	IGlobalContentPackage.providedBy(package):
			continue
		seen.add(package.ntiid)
		_recur(package)

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

		# Load library
		library = component.queryUtility(IContentPackageLibrary)
		if library is not None:
			library.syncContentPackages()

		seen = set()
		for current_site in get_all_host_sites():
			with site(current_site):
				_process_site(seen, current_site, intids)

		logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to 29 by updating the asset storage
	"""
	do_evolve(context, generation)
