#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 46

from zope import component
from zope import interface

from zope.component.hooks import setHooks
from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IEditableContentPackage

from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites


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


def _process_library(library, intids, seen):

    def _recur(unit, courses):
        container = IPresentationAssetContainer(unit)
        for asset in list(container.assets()):
            if IUserCreatedAsset.providedBy(asset):
                container.pop(asset.ntiid)
                if IContentUnit.providedBy(asset.__parent__):
                    asset.__parent__ = courses[0] # pick first
        for child in unit.children or ():
            _recur(child, courses)

    for package in library.contentPackages or ():
        doc_id = intids.queryId(package)
        if doc_id is None or doc_id in seen:
            continue
        seen.add(doc_id)
        if not IEditableContentPackage.providedBy(package):
            courses = get_courses_for_packages(packages=package.ntiid, 
                                               intids=intids)
            _recur(package, courses)


def _process_site(current, intids, seen):
    with current_site(current):
        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            _process_library(library, intids, seen)


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

        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            library.syncContentPackages()

        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)

        for current in get_all_host_sites():
            _process_site(current, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Dataserver evolution %s done.', generation)


def evolve(context):
    """
    Evolve to gen 46 to clean up all created assets from pkg containers
    """
    do_evolve(context)
