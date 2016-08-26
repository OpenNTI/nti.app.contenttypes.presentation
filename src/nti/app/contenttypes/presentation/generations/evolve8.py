#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 8

import functools

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from zope.component.hooks import site
from zope.component.hooks import setHooks

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_courses

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import CATALOG_INDEX_NAME

from nti.contentlibrary.indexed_data.interfaces import IContainedObjectCatalog

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import run_job_in_all_host_sites

ITEM_INTERFACES = (INTIAudio, INTIVideo, INTITimeline, INTISlideDeck, INTIRelatedWorkRef)

@interface.implementer(IDataserver)
class MockDataserver(object):

	root = None

	def get_by_oid(self, oid, ignore_creator=False):
		resolver = component.queryUtility(IOIDResolver)
		if resolver is None:
			logger.warn("Using dataserver without a proper ISiteManager configuration.")
		else:
			return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
		return None

def _reindex_items(catalog, intids):
	library = component.queryUtility(IContentPackageLibrary)
	if library is None:
		return

	registry = get_registry()
	for provided in ITEM_INTERFACES:
		for _, item in registry.getUtilitiesFor(provided):
			courses = list(get_presentation_asset_courses(item) or ())
			course = courses[0] if courses else None
			if course is None:
				continue

			packs = get_course_packages(course)
			if not packs:
				continue

			content_package = packs[0]
			catalog.index(item, container_ntiids=content_package.ntiid,
					  	  namespace=content_package.ntiid)

			if INTISlideDeck.providedBy(item):
				extended = (content_package.ntiid, item.ntiid)
				for slide in item.Slides or ():
					catalog.index(slide, container_ntiids=extended,
						  		  namespace=content_package.ntiid)

				for video in item.Videos or ():
					catalog.index(video, container_ntiids=extended,
						  		  namespace=content_package.ntiid)

def do_evolve(context):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = dataserver_folder
	component.provideUtility(mock_ds, IDataserver)

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
	Evolve to 8 by fixing index for items.
	"""
	do_evolve(context)
