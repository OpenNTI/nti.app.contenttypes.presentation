#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 34

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import IAssetRef

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

from nti.site.utils import unregisterUtility

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

def _unregister_refs(current_site, intids, seen):
	result = 0
	registry = current_site.getSiteManager()
	for name, item in list(registry.getUtilitiesFor(IAssetRef)):
		if name in seen:
			continue
		seen.add(name)

		provided = iface_of_asset(item)
		if unregisterUtility(registry, provided=provided, name=name):
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
			
		result = 0
		seen = set()
		logger.info('Evolution %s started.', generation)
		
		for current_site in get_all_host_sites():
			with site(current_site):
				result += _unregister_refs(current_site, intids, seen)

		logger.info('Evolution %s done. %s item(s) unregistered',
					generation, result)

def evolve(context):
	"""
	Evolve to 33 by removing asset ref objects from registry
	"""
	do_evolve(context, generation)
