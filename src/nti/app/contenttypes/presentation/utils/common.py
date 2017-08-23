#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import lifecycleevent

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.contentlibrary.utils import yield_content_packages

from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentUnit

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import interface_of_asset

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IItemAssetContainer
from nti.contenttypes.presentation.interfaces import ILegacyPresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.interfaces import LocatedExternalDict

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import remove_transaction_history

from nti.site.hostpolicy import get_all_host_sites

from nti.site.interfaces import IHostPolicyFolder

from nti.site.utils import registerUtility

from nti.traversal.traversal import find_interface


def yield_sync_courses(ntiids=()):
    catalog = component.getUtility(ICourseCatalog)
    if not ntiids:
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            if     course is None \
                or ILegacyCourseInstance.providedBy(course) \
                or ICourseSubInstance.providedBy(course):
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


def presentation_assets(registry=component):
    for ntiid, item in registry.getUtilitiesFor(IPresentationAsset):
        if not ILegacyPresentationAsset.providedBy(item):
            yield ntiid, item


# remove invalid assets


def remove_asset(ntiid, asset, registry, container=None, catalog=None):
    if container is not None:
        container.pop(ntiid, None)
    remove_transaction_history(asset)
    remove_presentation_asset(asset, registry, catalog, ntiid)


def remove_invalid_assets(removed=None, seen=None):
    count = 0
    site_name = getSite().__name__
    catalog = get_library_catalog()
    registry = component.getSiteManager()
    intids = component.getUtility(IIntIds)
    # get defaults
    seen = set() if seen is None else seen
    removed = set() if removed is None else removed
    # loop and check
    for ntiid, item in list(presentation_assets()):
        provided = interface_of_asset(item)
        doc_id = intids.queryId(item)
        if doc_id in seen:
            continue
        count += 1
        # check invalid registration
        if doc_id is None:
            logger.warn("Removing invalid registration (%s,%s) from site %s",
                        provided.__name__, ntiid, site_name)
            removed.add(ntiid)
            remove_asset(ntiid, item, registry, catalog=catalog)
            continue
        # check unreachable asset
        if      IItemAssetContainer.providedBy(item) \
            and not has_a_valid_parent(item, intids):
            logger.warn("Removing unreachable (%s,%s) from site %s",
                        provided.__name__, ntiid, site_name)
            removed.add(ntiid)
            remove_asset(ntiid, item, registry, catalog=catalog)
            continue
        # check asset references
        if      IAssetRef.providedBy(item) \
            and not INTIDiscussionRef.providedBy(item) \
            and find_object_with_ntiid(item.target or '') is None:
            logger.warn("Removing invalid asset ref (%s to %s) from site %s",
                        ntiid, item.target, site_name)
            removed.add(ntiid)
            remove_asset(ntiid, item, registry, catalog=catalog)
            continue
        # track
        seen.add(doc_id)
    logger.info("%s asset(s) found in %s", count, site_name)
    # return
    return removed, seen


def remove_all_invalid_assets():
    seen = set()
    result = LocatedExternalDict()
    for current in get_all_host_sites():
        removed = set()
        with current_site(current):
            remove_invalid_assets(removed, seen)
        result[current.__name__] = sorted(removed)
    return result


# remove inaccessible assets


def context_site(context):
    site = IHostPolicyFolder(context, None)
    return site if site is not None else getSite()


def context_assets(context):
    container = IPresentationAssetContainer(context)
    if getattr(container, '__parent__', None) is None:
        container.__parent__ = context
    for key, value in list(container.items()):  # snapshot
        yield key, value, container
course_assets = context_assets  # BWC


def check_asset_container(context, removed=None, master=None):
    """
    clean context asset container by removing those assets that either
    don't have an intid or cannot be found in the registry
    or don't have proper lineage
    """
    site = context_site(context)
    catalog = get_library_catalog()
    registry = site.getSiteManager()
    intids = component.getUtility(IIntIds)
    master = set() if master is None else master
    removed = set() if removed is None else removed
    for ntiid, asset, container in context_assets(context):
        doc_id = intids.queryId(asset)
        if doc_id in master:
            continue
        provided = interface_of_asset(asset)
        # check it can be found in registry
        registered = registry.queryUtility(provided, name=ntiid)
        if registered is None:
            remove_asset(ntiid, asset, registry, container, catalog)
            removed.add(ntiid)
        # check it has a valid uid and parent
        elif doc_id is None or not has_a_valid_parent(asset, intids):
            remove_asset(ntiid, asset, registry, container, catalog)
            removed.add(ntiid)
        else:
            master.add(doc_id)
    return master


def remove_inaccessible_assets(seen=None, master=None):
    removed = set()
    catalog = get_library_catalog()
    intids = component.getUtility(IIntIds)
    seen = set() if seen is None else seen
    master = set() if master is None else master
    # loop through all courses and check their
    # asset containers
    for course in yield_sync_courses():
        doc_id = intids.queryId(course)
        if doc_id in seen:
            continue
        seen.add(doc_id)
        check_asset_container(course, removed, master)
    # look all content units and check their
    # asset containers
    def _recur(context):
        doc_id = intids.queryId(context)
        if doc_id is None or doc_id in seen:
            return
        seen.add(doc_id)
        check_asset_container(context, removed, master)
        for child in context.children or ():
            _recur(child)
    for package in yield_content_packages():
        _recur(package)
    # unregister those utilities that cannot be found in the containers
    site = getSite()
    registered = set()
    registry = site.getSiteManager()
    for ntiid, asset in list(presentation_assets()):
        doc_id = intids.queryId(asset)
        if doc_id is None or doc_id not in master:
            remove_asset(ntiid, asset, registry, catalog=catalog)
            removed.add(ntiid)
        elif doc_id not in seen:
            seen.add(doc_id)
            registered.add(doc_id)
    # unindex invalid entries in catalog
    references = catalog.get_references(sites=site.__name__)
    for uid in references or ():
        asset = intids.queryObject(uid)
        if asset is None or not IPresentationAsset.providedBy(asset):
            catalog.unindex(uid)
        else:
            ntiid = asset.ntiid
            provided = interface_of_asset(asset)
            if registry.queryUtility(provided, name=ntiid) is None:
                remove_asset(ntiid, asset, registry, catalog=catalog)
                removed.add(ntiid)
    # prepare result
    result = LocatedExternalDict()
    result['Removed'] = sorted(removed)
    result['TotalContainedAssets'] = len(master)
    result['TotalRegisteredAssets'] = len(registered)
    result['Difference'] = sorted(master.difference(registered))
    return result


def remove_all_inaccessible_assets():
    seen = set()
    master = set()
    result = LocatedExternalDict()
    for current in get_all_host_sites():
        with current_site(current):
            removed = remove_inaccessible_assets(seen, master)
            result[current.__name__] = removed
    return result


# fix inaccessible assets


def fix_inaccessible_assets(seen=None):
    result = set()
    site_assets = {}
    catalog = get_library_catalog()
    # gather all site registered assets
    registry = component.getSiteManager()
    for ntiid, asset in presentation_assets():
        site_assets[ntiid] = asset

    containers = {}
    seen = set() if seen is None else seen
    intids = component.getUtility(IIntIds)

    # gather all courses
    for course in yield_sync_courses():
        doc_id = intids.queryId(course)
        if doc_id is None or doc_id in seen:
            continue
        seen.add(doc_id)
        for key, value, container in context_assets(course):
            containers[key] = (value, container)

    # gather all content units
    def _recur(context):
        doc_id = intids.queryId(context)
        if doc_id is None or doc_id in seen:
            return
        seen.add(doc_id)
        for key, value, container in context_assets(course):
            containers[key] = (value, container)
        for child in context.children or ():
            _recur(child)

    for package in yield_content_packages():
        _recur(package)

    if not containers:
        return result

    # check containers
    for ntiid, data in containers.items():
        item, container = data
        # skip invalid containers
        if      IItemAssetContainer.providedBy(item) \
            and not has_a_valid_parent(item, intids):
            continue
        parent = find_interface(container, ICourseInstance, strict=False)
        if parent is None:
            parent = find_interface(container, IContentUnit, strict=False)
            namespace = getattr(parent, 'ntiid', None)
        else:
            entry = ICourseCatalogEntry(parent)
            namespace = entry.ntiid
        site = context_site(parent)
        doc_id = intids.queryId(item)
        provided = interface_of_asset(item)
        # check registration
        if ntiid not in site_assets:
            result.add(ntiid)
            logger.warn("Registering %s/%s", ntiid, namespace)
            registerUtility(registry, item, provided, name=ntiid)
        # check intid. if none it means it was posibly deleted
        # but we want to restore it
        if doc_id is None:
            result.add(ntiid)
            doc_id = intids.register(item)
            logger.warn("Assigning intid to %s/%s", ntiid, namespace)
            # best effort index
            catalog.index(item,
                          namespace=namespace,
                          sites=site.__name__,
                          container_ntiids=namespace)

    # check registered assets
    for ntiid, item in site_assets.items():
        # skip invalid containers
        if      IItemAssetContainer.providedBy(item) \
            and not has_a_valid_parent(item, intids):
            continue
        namespace = None
        must_index = False
        doc_id = intids.queryId(item)
        if doc_id is None:
            must_index = True
            result.add(ntiid)
            doc_id = intids.register(item)
            logger.warn("Assigning intid to %s", ntiid)
        container = None
        data = containers.get(ntiid)
        if data is not None:
            value, container = data
            if value is not item:
                container[ntiid] = item
        if container is None:
            parent = find_interface(container, ICourseInstance, strict=False)
            if parent is None:
                parent = find_interface(container, IContentUnit, strict=False)
                namespace = getattr(parent, 'ntiid', None)
            else:
                entry = ICourseCatalogEntry(parent)
                namespace = entry.ntiid
            container = IPresentationAssetContainer(parent, None)
            if container is not None:
                result.add(ntiid)
                container[ntiid] = item
                logger.warn("Adding to container %s/%s", ntiid, namespace)
                must_index = True
        if must_index:
            catalog.index(item,
                          namespace=namespace,
                          sites=site.__name__,
                          container_ntiids=namespace)
    # signal modifications and return
    for asset in result:
        lifecycleevent.modified(asset)
    return result


def fix_all_inaccessible_assets():
    seen = set()
    result = LocatedExternalDict()
    for current in get_all_host_sites():
        with current_site(current):
            fixed = fix_inaccessible_assets(seen)
            result[current.__name__] = sorted(fixed)
    return result
