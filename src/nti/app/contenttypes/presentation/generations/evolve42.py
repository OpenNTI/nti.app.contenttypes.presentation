#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 42

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.courses.common import get_course_packages

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


def process_course(course, intids):
    result = 0
    course_container = IPresentationAssetContainer(course)
    for package in get_course_packages(course):
        # only look at root
        package_container = IPresentationAssetContainer(package)
        for asset in list(package_container.assets()):
            if IUserCreatedAsset.providedBy(asset):
                doc_id = intids.queryId(asset)
                package_container.pop(asset.ntiid, None)
                if doc_id is None:
                    course_container.pop(asset.ntiid, None)
                elif asset.ntiid not in course_container:
                    course_container.append(asset)
                    result += 1
    return result


def _process_site(current, intids, seen):
    result = 0
    with current_site(current):
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is None or catalog.isEmpty():
            return result
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            result += process_course(course, intids)
    return result


def do_evolve(context, generation=generation):
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    result = 0
    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        seen = set()
        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)
        for current in get_all_host_sites():
            result += _process_site(current, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done. %s asset(s) moved',
                generation, result)
    return result


def evolve(context):
    """
    Evolve to generation 42 by removing user created assets from the course pkgs
    """
    do_evolve(context)
