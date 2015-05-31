#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 2

from zope.component.hooks import setHooks

from nti.common.time import time_to_64bit_int

from .. import CATALOG_INDEX_NAME

from ..interfaces import IPresentationAssetsIndex

def do_evolve(context):
	setHooks()
	conn = context.connection
	root = conn.root()

	dataserver_folder = root['nti.dataserver']
	lsm = dataserver_folder.getSiteManager()
	index = lsm.getUtility(IPresentationAssetsIndex, name=CATALOG_INDEX_NAME)
	for k, v in list(index._last_modified.items()):
		index._last_modified[k] = time_to_64bit_int(v)

def evolve(context):
	"""
	Evolve to generation 2 by adjusting the last mod valued
	"""
	do_evolve(context)
