#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 4

from zope.component.hooks import setHooks

from ..interfaces import IPresentationAssetsIndex

from .. import CATALOG_INDEX_NAME

def reset_catalog(dataserver_folder):
	lsm = dataserver_folder.getSiteManager()
	catalog = lsm.queryUtility(IPresentationAssetsIndex, name=CATALOG_INDEX_NAME)
	if catalog is not None:
		catalog.reset()

def do_evolve(context):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']
	reset_catalog(dataserver_folder)

def evolve(context):
	"""
	Evolve to generation 4 by resetting catalog
	"""
	do_evolve(context)
