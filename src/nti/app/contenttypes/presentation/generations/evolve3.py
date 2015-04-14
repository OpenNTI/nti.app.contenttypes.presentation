#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 3

from zope.intid import IIntIds

from zope.component.hooks import setHooks

from ..interfaces import IPresentationAssetsIndex

from ..index import install_catalog

from .. import CATALOG_INDEX_NAME

def do_evolve(context):
	setHooks()
	conn = context.connection
	root = conn.root()

	dataserver_folder = root['nti.dataserver']
	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(IIntIds)

	## remove old utility
	catalog = lsm.getUtility(IPresentationAssetsIndex, name=CATALOG_INDEX_NAME)
	lsm.unregisterUtility(IPresentationAssetsIndex, name=CATALOG_INDEX_NAME)
	intids.unregister(catalog)

	## recreate new one
	install_catalog(context)
		
def evolve(context):
	"""
	Evolve to generation 3 by recreating catalog
	"""
	do_evolve(context)
