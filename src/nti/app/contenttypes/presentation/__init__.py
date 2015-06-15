#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from .interfaces import IPresentationAssetsIndex

VIEW_OVERVIEW_CONTENT = "overview-content"

CATALOG_INDEX_NAME = '++etc++contenttypes.presentation-index'

def iface_of_thing(item):
	for iface in ALL_PRESENTATION_ASSETS_INTERFACES:
		if iface.providedBy(item):
			return iface
	return None
