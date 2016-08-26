#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 7

from zope.component.hooks import setHooks

from zope.intid import IIntIds

from nti.app.contenttypes.presentation.generations import PA_INDEX_NAME

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetsIndex

from nti.contentlibrary.indexed_data import CATALOG_INDEX_NAME as LIB_INDEX_NAME

from nti.contentlibrary.indexed_data.interfaces import IContainedObjectCatalog

def do_evolve(context):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(IIntIds)
	pa_catalog = lsm.queryUtility(IPresentationAssetsIndex, name=PA_INDEX_NAME)
	if pa_catalog is None:
		return  # pragma no cover

	lib_catalog = lsm.getUtility(IContainedObjectCatalog, name=LIB_INDEX_NAME)

	# move data
	src_index = pa_catalog._last_modified
	tgt_index = lib_catalog._last_modified
	for key, value in src_index.items():
		tgt_index[key] = value

	pa_catalog.__parent__ = None
	intids.unregister(pa_catalog)
	lsm.unregisterUtility(pa_catalog, provided=IPresentationAssetsIndex,
						  name=PA_INDEX_NAME)

	if hasattr(pa_catalog, 'items'):
		for name, index in list(pa_catalog.items()):
			del pa_catalog[name]
			intids.unregister(index)

def evolve(context):
	"""
	Evolve to generation 7 by removing index
	"""
	do_evolve(context)
