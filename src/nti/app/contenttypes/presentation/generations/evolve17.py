#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 17

from zope import component

from zope.component.hooks import site
from zope.component.hooks import site as current_site

from nti.app.contentlibrary.utils import yield_sync_content_packages

from nti.contentlibrary.interfaces import IContentUnit

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.site.hostpolicy import get_all_host_sites

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

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		for site in get_all_host_sites():
			with current_site(site):
				registry = component.getSiteManager()
				_process_pacakges(registry)

	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 17 by setting lineage of package assets
	"""
	do_evolve(context, generation)
