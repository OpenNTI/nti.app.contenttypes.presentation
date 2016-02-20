#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from collections import OrderedDict

from zope import component

from zope.interface.adapter import _lookupAll as zopeLookupAll

from zope.intid.interfaces import IIntIds

from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import get_all_host_sites

from nti.site.utils import unregisterUtility

def yield_sync_courses(ntiids=()):
	catalog = component.getUtility(ICourseCatalog)
	if not ntiids:
		for entry in catalog.iterCatalogEntries():
			course = ICourseInstance(entry, None)
			if 		course is None \
				or	ILegacyCourseInstance.providedBy(course) \
				or	ICourseSubInstance.providedBy(course):
				continue
			yield course
			for subinstance in get_course_subinstances(course):
				yield subinstance
	else:
		for ntiid in ntiids:
			obj = find_object_with_ntiid(ntiid)
			course = ICourseInstance(obj, None)
			if course is None or ILegacyCourseInstance.providedBy(course):
				logger.error("Could not find course with NTIID %s", ntiid)
			else:
				yield course

def lookup_all_presentation_assets(site_registry):
	result = {}
	required = ()
	order = len(required)
	for registry in site_registry.utilities.ro:  # must keep order
		byorder = registry._adapters
		if order >= len(byorder):
			continue
		components = byorder[order]
		extendors = ALL_PRESENTATION_ASSETS_INTERFACES
		zopeLookupAll(components, required, extendors, result, 0, order)
		break  # break on first
	return result

def has_a_valid_parent(item, intids):
	parent = item.__parent__
	doc_id = intids.queryId(parent) if parent is not None else None
	return parent is not None and doc_id is not None

def remove_site_invalid_assets(current, intids=None, catalog=None, seen=None):
	removed = set()
	site_name = current.__name__
	registry = current.getSiteManager()

	# get defaults
	seen = set() if seen is None else seen
	catalog = get_library_catalog() if catalog is None else catalog
	intids = component.getUtility(IIntIds) if intids is None else intids

	# get all assets in site/no hierarchy
	site_components = lookup_all_presentation_assets(registry)
	logger.info("%s asset(s) found in %s", len(site_components), site_name)

	for ntiid, item in site_components.items():
		provided = iface_of_asset(item)
		doc_id = intids.queryId(item)

		# registration for a removed asset
		if doc_id is None:
			logger.warn("Removing invalid registration %s from site %s", ntiid, site_name)
			removed.add(ntiid)
			remove_presentation_asset(item, registry, catalog, package=False)
			continue

		# invalid lesson overview
		if INTILessonOverview.providedBy(item) and not has_a_valid_parent(item, intids):
			logger.warn("Removing invalid lesson overview %s from site %s",
						ntiid, site_name)
			removed.add(ntiid)
			remove_presentation_asset(item, registry, catalog, package=False)
			continue

		# invalid overview groups overview
		if INTICourseOverviewGroup.providedBy(item) and not has_a_valid_parent(item, intids):
			logger.warn("Removing invalid course overview %s from site %s",
						ntiid, site_name)
			remove_presentation_asset(item, registry, catalog, package=False)
			continue

		# invalid media roll overview
		if INTIMediaRoll.providedBy(item) and not has_a_valid_parent(item, intids):
			logger.warn("Removing invalid media roll %s from site %s",
						ntiid, site_name)
			removed.add(ntiid)
			remove_presentation_asset(item, registry, catalog)
			continue

		# registration not in base site
		if ntiid in seen:
			removed.add(ntiid)
			logger.warn("Removing %s from site %s", ntiid, site_name)
			unregisterUtility(registry, provided=provided, name=ntiid)

		seen.add(ntiid)
	return removed

def remove_all_invalid_assets():
	seen = set()
	result = OrderedDict()
	catalog = get_library_catalog()
	intids = component.getUtility(IIntIds)
	for current in get_all_host_sites():
		removed = remove_site_invalid_assets(current, intids, catalog, seen)
		result[current.__name__] = sorted(removed)
	return result
