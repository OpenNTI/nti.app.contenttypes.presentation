#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.intid

from zope import component
from zope.component.hooks import site as current_site

from zope.traversing.interfaces import IEtcNamespace

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.site.interfaces import IHostPolicySiteManager

def remove_utilities(interfaces=ALL_PRESENTATION_ASSETS_INTERFACES, registry=component):
	count = 0
	intids = registry.getUtility(zope.intid.IIntIds)
	sites = registry.getUtility(IEtcNamespace, name='hostsites')
	for site in sites.values():
		with current_site(site):
			site_manager = site.getSiteManager()
			if IHostPolicySiteManager.providedBy(site_manager):
				unregister = site_manager.subscribedUnregisterUtility
			else:
				unregister = site_manager.unregisterUtility
			
			for provided in interfaces or ():
				for name, comp in list(site_manager.getUtilitiesFor(provided)):
					unregister(provided=provided, name=name)
					try:
						intids.unregister(comp)
					except KeyError:
						pass
					count +=1 
	return count
