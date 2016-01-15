#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from functools import partial

from zope import component

from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.metadata.predicates import BasePrincipalObjects

from nti.site.hostpolicy import run_job_in_all_host_sites

@component.adapter(ISystemUserPrincipal)
class _PresentationAssetObjects(BasePrincipalObjects):

	def iter_assets(self, result, seen):
		for _, item in list(component.getUtilitiesFor(IPresentationAsset)):
			if item.ntiid not in seen:
				seen.add(item.ntiid)
				result.append(item)

	def iter_objects(self):
		result = []
		seen = set()
		run_job_in_all_host_sites(partial(self.iter_assets, result, seen))
		return result
