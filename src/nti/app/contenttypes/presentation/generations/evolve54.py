#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

logger = __import__('logging').getLogger(__name__)

generation = 54

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.contenttypes.presentation.lesson import CONSTRAINT_ANNOTATION_KEY

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


def _process_site(current, seen):
    result = 0
    with current_site(current):
        for name, lesson in list(component.getUtilitiesFor(INTILessonOverview)):
            if name in seen:
                continue
            seen.add(name)
            try:
                annotations = lesson.__annotations__
                constraint_container = annotations[CONSTRAINT_ANNOTATION_KEY]
                if constraint_container.__parent__ is None:
                    logger.info('Updating lineage for lesson constraint container (%s)',
                                lesson.ntiid)
                    constraint_container.__parent__ = lesson
            except (AttributeError, KeyError):
                pass
    return result


def do_evolve(context, generation=generation):
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        seen = set()
        for current in get_all_host_sites():
            _process_site(current, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 54 by making sure the constraint container has
    lineage.
    """
    do_evolve(context)
