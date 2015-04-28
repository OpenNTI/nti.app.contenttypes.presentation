#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 4

import zope.intid

from zope.component.hooks import setHooks
from zope.component.hooks import site as current_site

from zope.traversing.interfaces import IEtcNamespace

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.site.interfaces import IHostPolicySiteManager

from ..interfaces import IPresentationAssetsIndex

from .. import CATALOG_INDEX_NAME

def reset_catalog(dataserver_folder):
	lsm = dataserver_folder.getSiteManager()
	catalog = lsm.getUtility(IPresentationAssetsIndex, name=CATALOG_INDEX_NAME)
	catalog.reset()

def remove_utilities(dataserver_folder, interfaces=ALL_PRESENTATION_ASSETS_INTERFACES):
	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(zope.intid.IIntIds)
	sites = lsm.getUtility(IEtcNamespace, name='hostsites')
	for site in sites.values():
		with current_site(site):
			registry = site.getSiteManager()
			if IHostPolicySiteManager.providedBy(registry):
				unregister = registry.subscribedUnregisterUtility
			else:
				unregister = registry.unregisterUtility
			
			for provided in interfaces or ():
				for name, comp in list(registry.getUtilitiesFor(provided)):
					unregister(provided=provided, name=name)
					try:
						intids.unregister(comp)
					except KeyError:
						pass

def do_evolve(context):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']
	reset_catalog(dataserver_folder)
	remove_utilities(dataserver_folder)

def evolve(context):
	"""
	Evolve to generation 4 by resetting catalog
	"""
	do_evolve(context)
