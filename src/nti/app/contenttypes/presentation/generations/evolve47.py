#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 47

from zope import component
from zope import interface

from zope.component.hooks import setHooks
from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.contentlibrary.utils import yield_content_packages

from nti.app.contenttypes.presentation.utils.common import yield_sync_courses

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

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


def _process_site(intids, seen):
    # process courses
    for course in yield_sync_courses():
        doc_id = intids.queryId(course)
        if doc_id is None or doc_id in seen:
            continue
        seen.add(doc_id)
        container = IPresentationAssetContainer(course)
        if getattr(container, '__parent__', None) is None:
            container.__parent__ = course

    # process content pkgs
    def _recur(context):
        doc_id = intids.queryId(context)
        if doc_id is None or doc_id in seen:
            return
        seen.add(doc_id)
        # fix container
        container = IPresentationAssetContainer(context)
        if getattr(container, '__parent__', None) is None:
            container.__parent__ = context
        # examine children
        for child in context.children or ():
            _recur(child)

    for package in yield_content_packages():
        _recur(package)


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

        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            library.syncContentPackages()

        for current in get_all_host_sites():
            with current_site(current):
                _process_site(intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Dataserver evolution %s done. %s container(s) checked',
                generation, len(seen))


def evolve(context):
    """
    Evolve to gen 47 to fix asset container lineage
    """
    do_evolve(context)
