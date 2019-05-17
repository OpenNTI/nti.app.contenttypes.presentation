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

from zope.component.hooks import site as current_site

from nti.app.contenttypes.presentation.utils.asset import get_component_site_name

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.contenttypes.presentation.lesson import CONSTRAINT_ANNOTATION_KEY

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.ntiids.oids import to_external_ntiid_oid

from nti.traversal.traversal import find_interface

from nti.site.hostpolicy import get_all_host_sites

generation = 55

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warning("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator)
        return None


def _process_site(current, catalog, seen):
    result = 0
    with current_site(current):
        for name, group in list(component.getUtilitiesFor(INTICourseOverviewGroup)):
            if name in seen:
                continue
            seen.add(name)

            lesson = group.__parent__
            if lesson is None:
                continue

            course = find_interface(lesson, ICourseInstance, strict=False)
            if course is None or ILegacyCourseInstance.providedBy(course):
                continue

            entry = ICourseCatalogEntry(course)
            namespace = to_external_ntiid_oid(lesson)
            container_ntiids = (lesson.ntiid, entry.ntiid)
            # Can not use current site for indexing group which may be registered in parent site, if we happen to process
            # the child site first (then parent site), it can not be found in parent site when searching the index based on site name.
            site_name = get_component_site_name(group,
                                                INTICourseOverviewGroup,
                                                name=group.ntiid)
            catalog.index(group,
                          container_ntiids=container_ntiids,
                          namespace=namespace,
                          sites=site_name)
            result += 1
    return result


def do_evolve(context, generation=generation):  # pylint: disable=redefined-outer-name
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
        catalog = get_library_catalog()
        for current in get_all_host_sites():
            result += _process_site(current, catalog, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done, %s groups re-indexed.', generation, result)


def evolve(context):
    """
    Evolve to generation 55 by setting correct namespace/container_ntiids and indexing all INTICourseOverviewGroup objects.
    """
    do_evolve(context)
