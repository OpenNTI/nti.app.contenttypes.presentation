#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

VIEW_OVERVIEW_CONTENT = "overview-content"

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

def iface_of_thing(item):
	for iface in ALL_PRESENTATION_ASSETS_INTERFACES:
		if iface.providedBy(item):
			return iface
	return None
