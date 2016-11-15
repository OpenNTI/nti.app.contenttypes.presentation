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
from zope.component.hooks import site as current_site

from zope.interface.adapter import _lookupAll as zopeLookupAll # Private func

from zope.intid.interfaces import IIntIds

from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.presentation import COURSE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IItemAssetContainer
from nti.contenttypes.presentation.interfaces import ICoursePresentationAsset
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.courses.common import get_course_site

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import remove_transaction_history

from nti.site.hostpolicy import get_host_site
from nti.site.hostpolicy import get_all_host_sites

from nti.site.site import get_component_hierarchy_names

ITEMS = StandardExternalFields.ITEMS
INTID = StandardExternalFields.INTID
NTIID = StandardExternalFields.NTIID
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

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

def has_a_valid_parent(item, intids):
	parent = item.__parent__
	doc_id = intids.queryId(parent) if parent is not None else None
	return parent is not None and doc_id is not None

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

	with current_site(current):
		for ntiid, item in site_components.items():
			provided = iface_of_asset(item)
			doc_id = intids.queryId(item)
	
			# registration for a removed asset
			if doc_id is None:
				logger.warn("Removing invalid registration (%s,%s) from site %s",
							provided.__name__, ntiid, site_name)
				removed.add(ntiid)
				remove_presentation_asset(item, registry, catalog, name=ntiid)
				continue
	
			if IItemAssetContainer.providedBy(item) and not has_a_valid_parent(item, intids):
				logger.warn("Removing unreachable (%s,%s) from site %s",
							provided.__name__, ntiid, site_name)
				removed.add(ntiid)
				remove_presentation_asset(item, registry, catalog, name=ntiid)
				continue
	
			if 		(	INTIRelatedWorkRefPointer.providedBy(item) 
					 or INTIAssessmentRef.providedBy(item) 
					 or INTITimelineRef.providedBy(item)) \
				and find_object_with_ntiid(item.target) is None:
					logger.warn("Removing invalid asset ref (%s to %s) from site %s",
								ntiid, item.target, site_name)
					removed.add(ntiid)
					remove_presentation_asset(item, registry, catalog, name=ntiid)
					continue
			# track
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

def course_assets(course):
	container = IPresentationAssetContainer(course)
	for key, value in list(container.items()):  # snapshot
		if ICoursePresentationAsset.providedBy(value):
			yield key, value, container

def remove_course_inaccessible_assets():
	sites = set()
	master = set()
	items = list()
	registered = set()
	result = LocatedExternalDict()
	catalog = get_library_catalog()
	intids = component.getUtility(IIntIds)
	all_courses = list(yield_sync_courses())

	# clean containers by removing those assets that either
	# don't have an intid or cannot be found in the registry
	# or don't have proper lineage
	for course in all_courses:
		# check every object in the course
		site_name = get_course_site(course)
		registry = get_host_site(site_name).getSiteManager()
		for ntiid, asset, container in course_assets(course):
			uid = intids.queryId(asset)
			provided = iface_of_asset(asset)
			# check it can be found in registry
			if registry.queryUtility(provided, name=ntiid) is None:
				container.pop(ntiid, None)
				remove_transaction_history(asset)
				remove_presentation_asset(asset, registry, catalog, name=ntiid)
			# check it has a valid uid and parent
			elif uid is None or not has_a_valid_parent(asset, intids):
				container.pop(ntiid, None)
				remove_transaction_history(asset)
			else:
				master.add(ntiid)
		sites.add(site_name)

	# always have sites
	sites = get_component_hierarchy_names() if not all_courses else sites

	# unregister those utilities that cannot be found in the course containers
	for site in sites:
		registry = get_host_site(site).getSiteManager()
		for ntiid, asset in lookup_all_presentation_assets(registry).items():
			if not ICoursePresentationAsset.providedBy(asset):
				continue
			uid = intids.queryId(asset)
			if uid is None or ntiid not in master:
				remove_transaction_history(asset)
				remove_presentation_asset(asset, registry, catalog, name=ntiid)
				items.append({
					INTID:uid,
					NTIID:ntiid,
					MIMETYPE:asset.mimeType,
				})
			else:
				registered.add(ntiid)

	# unindex invalid entries in catalog
	references = catalog.get_references(sites=sites,
									 	provided=COURSE_CONTAINER_INTERFACES)
	for uid in references or ():
		asset = intids.queryObject(uid)
		if asset is None or not IPresentationAsset.providedBy(asset):
			catalog.unindex(uid)
		else:
			ntiid = asset.ntiid
			provided = iface_of_asset(asset)
			if component.queryUtility(provided, name=ntiid) is None:
				remove_transaction_history(asset)
				remove_presentation_asset(asset, catalog=catalog, name=ntiid)
				items.append({
					INTID:uid,
					NTIID:ntiid,
					MIMETYPE:asset.mimeType,
				})

	items.sort(key=lambda x:x[NTIID])
	result[ITEMS] = items
	result['Sites'] = list(sites)
	result['TotalContainedAssets'] = len(master)
	result['TotalRegisteredAssets'] = len(registered)
	result['Difference'] = sorted(master.difference(registered))
	result[ITEM_COUNT] = result[TOTAL] = len(items)
	return result
