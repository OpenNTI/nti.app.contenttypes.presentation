#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 12

import functools

from zope import component

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds
	
from nti.contentlibrary.indexed_data import CATALOG_INDEX_NAME
from nti.contentlibrary.indexed_data.interfaces import IContainedObjectCatalog

from nti.contenttypes.presentation.interfaces import INTISlideDeck

from nti.site.hostpolicy import run_job_in_all_host_sites

def _reindex_items(catalog, intids):
	for ntiid, deck in list(component.getUtilitiesFor(INTISlideDeck)):
		for slide in deck.Slides or ():
			catalog.index(slide, container_ntiids=ntiid)
		for video in deck.Videos or ():
			catalog.index(video, container_ntiids=ntiid)
			
def do_evolve(context, generation=generation):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	with site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = dataserver_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		catalog = lsm.getUtility(IContainedObjectCatalog, name=CATALOG_INDEX_NAME)

		run_job_in_all_host_sites(functools.partial(_reindex_items, catalog, intids))
		logger.info('Evolution %s done.', generation)
		
def evolve(context):
	"""
	Evolve to gen 12 by reindexing containers of slidedecks
	"""
	do_evolve(context)
