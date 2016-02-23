#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 18

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import site as current_site

from nti.app.contentlibrary.utils import yield_sync_content_packages

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES

from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

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

def _pacakge_assets(pacakge):

	def recur(unit):
		for child in unit.children or ():
			recur(child)
		container = IPresentationAssetContainer(unit)
		for item in container.values():
			provided = iface_of_asset(item)
			if provided not in PACKAGE_CONTAINER_INTERFACES:
				continue
			if not item.__parent__ or not IContentUnit.providedBy(item.__parent__):
				item.__parent__ = pacakge
	recur(pacakge)

def _process_pacakges(registry):
	for pacakge in yield_sync_content_packages():
		_pacakge_assets(pacakge)

def _process_slidedecks(registry):
	for _, deck in list(registry.getUtilitiesFor(INTISlideDeck)):
		for item in deck.Items or ():
			item.__parent__ = deck

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = ds_folder
	component.provideUtility(mock_ds, IDataserver)

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		library = component.queryUtility(IContentPackageLibrary)
		if library is not None:
			library.syncContentPackages()

		for site in get_all_host_sites():
			with current_site(site):
				registry = component.getSiteManager()
				_process_pacakges(registry)
				_process_slidedecks(registry)

	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 18 by setting lineage of package assets
	"""
	do_evolve(context, generation)
