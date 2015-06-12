#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 6

from zope.component.hooks import setHooks

from .. import CATALOG_INDEX_NAME

from ..interfaces import IPresentationAssetsIndex

def do_evolve(context):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	lsm = dataserver_folder.getSiteManager()
	catalog = lsm.getUtility(IPresentationAssetsIndex, name=CATALOG_INDEX_NAME)

	for name in ('_type_index', '_entry_index', '_namespace_index'):
		if hasattr(catalog, name):
			delattr(catalog, name)

def evolve(context):
	"""
	Evolve to generation 6 by removing unused catalog indices
	"""
	do_evolve(context)
