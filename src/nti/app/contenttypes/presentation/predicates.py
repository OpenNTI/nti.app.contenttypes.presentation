#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.component.hooks import site as current_site

from zope.interface.adapter import _lookupAll as zopeLookupAll # Private func

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.metadata.predicates import BasePrincipalObjects

from nti.site.hostpolicy import get_all_host_sites

def lookup_all_presentation_assets(site_registry):
	result = {}
	required = ()
	order = len(required)
	for registry in site_registry.utilities.ro:  # must keep order
		byorder = registry._adapters
		if order >= len(byorder):
			continue
		components = byorder[order]
		extendors = ALL_PRESENTATION_ASSETS_INTERFACES
		zopeLookupAll(components, required, extendors, result, 0, order)
		break  # break on first
	return result

@component.adapter(ISystemUserPrincipal)
class _PresentationAssetObjects(BasePrincipalObjects):

	def iter_objects(self):
		result = []
		for site in get_all_host_sites():
			with current_site(site):
				registry = site.getSiteManager()
				site_components = lookup_all_presentation_assets(registry)
				result.extend(site_components.values())
		return result
