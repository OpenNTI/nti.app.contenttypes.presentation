#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 14

import functools

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from nti.contentlibrary.indexed_data import CATALOG_INDEX_NAME
from nti.contentlibrary.indexed_data.interfaces import IContainedObjectCatalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.coremetadata.interfaces import IPublishable
from nti.coremetadata.interfaces import IDefaultPublished

from nti.site.hostpolicy import run_job_in_all_host_sites

from nti.traversal.traversal import find_interface

from ..synchronizer import index_pacakge_assets

def _reindex_lesson(catalog, ntiid, lesson):
	course = find_interface(lesson, ICourseInstance, strict=False)
	entry = ICourseCatalogEntry(course, None)
	grp_ntiids = (ntiid,) + ((entry.ntiid,) if entry is not None else ())
	for group in lesson.Items or ():
		catalog.index(group, container_ntiids=grp_ntiids)
		item_ntiids = grp_ntiids + (group.ntiid,)
		for item in group.Items or ():
			catalog.index(item, container_ntiids=item_ntiids)

def _reindex_slidedeck(catalog, ntiid, deck):
	for slide in deck.Slides or ():
		catalog.index(slide, container_ntiids=ntiid)
	for video in deck.Videos or ():
		catalog.index(video, container_ntiids=ntiid)

def _index_package_assets(catalog):
	course_catalog = component.queryUtility(ICourseCatalog)
	if course_catalog is not None:
		for entry in course_catalog.iterCatalogEntries():
			course = ICourseInstance(entry, None)
			if course is not None and not ILegacyCourseInstance.providedBy(course):
				index_pacakge_assets(course, catalog=catalog)

def _process_assets(catalog):
	for ntiid, item in list(component.getUtilitiesFor(IPresentationAsset)):
		# set byline
		if not getattr(item, 'byline', None):
			item.byline = getattr(item, 'creator', None)

		# remove publish interface
		if not INTILessonOverview.providedBy(item):
			interface.noLongerProvides(item, IDefaultPublished)
		elif IPublishable.providedBy(item):
			item.publish()

		# reindex
		if INTILessonOverview.providedBy(item):
			_reindex_lesson(catalog, ntiid, item)
		elif INTISlideDeck.providedBy(item):
			_reindex_slidedeck(catalog, ntiid, item)

def _process(catalog):
	_process_assets(catalog)
	_index_package_assets(catalog)

def do_evolve(context, generation=generation):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	with site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = dataserver_folder.getSiteManager()
		catalog = lsm.getUtility(IContainedObjectCatalog, name=CATALOG_INDEX_NAME)

		run_job_in_all_host_sites(functools.partial(_process, catalog))
		logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to gen 14 by updating containers of the package assets
	"""
	do_evolve(context)
