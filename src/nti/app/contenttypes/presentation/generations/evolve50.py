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

from nti.contenttypes.presentation.index import install_assets_library_catalog

from nti.contenttypes.presentation.interfaces import IPresentationAsset

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


def _process_site(current, catalog, intids, seen):
    with current_site(current):
        for _, asset in list(component.getUtilitiesFor(IPresentationAsset)):
            doc_id = intids.queryId(asset)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            catalog.index_doc(doc_id, asset)


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
        catalog = install_assets_library_catalog(ds_folder, intids)
        for index in catalog.values():
            index.clear()
        for current in get_all_host_sites():
            _process_site(current, catalog, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Dataserver evolution %s done. %s assets(s) indexed',
                generation, len(seen))


def evolve(context):
    """
    Evolve to gen 50 to index all assets
    """
    # do_evolve(context)  DON'T install yet
