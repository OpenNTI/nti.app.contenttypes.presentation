#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.component.hooks import setHooks
from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_containers

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IEditableContentPackage

from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

generation = 50

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warn("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def _find_in_pacakge_asset_containers(ntiid, pacakge):
    result = []
    def _recur(unit):
        container = IPresentationAssetContainer(unit, None)
        if container and ntiid in container:
            result.append(unit)
        if not result:
            for child in unit.children or ():
                _recur(child)
    _recur(pacakge)
    return bool(result)


def _process_site(current, intids, seen):
    with current_site(current):
        for ntiid, asset in list(component.getUtilitiesFor(IPackagePresentationAsset)):
            doc_id = intids.queryId(asset)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            if not IContentBackedPresentationAsset.providedBy(asset):
                continue
            # find any content ``legacy``` pkg
            found = False
            for container in get_presentation_asset_containers(asset):
                if      IContentPackage.providedBy(container) \
                    and not IEditableContentPackage.providedBy(container):
                    found = _find_in_pacakge_asset_containers(ntiid, container)
                    if found:
                        break
            # if not found the asset cannot be marked as content back
            if not found:
                logger.info("Unmarking %s", ntiid)
                interface.noLongerProvides(asset, IContentBackedPresentationAsset)


def do_evolve(context, generation=generation):
    setHooks()
    conn = context.connection
    root = conn.root()
    ds_folder = root['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    seen = set()
    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)

        # Load library
        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            library.syncContentPackages()

        for current in get_all_host_sites():
            _process_site(current, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Dataserver evolution %s done.', generation)


def evolve(context):
    """
    Evolve to gen 50 by unmarked non-content-backed assets
    """
    do_evolve(context)
