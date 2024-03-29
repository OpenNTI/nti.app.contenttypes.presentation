#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 44

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from ZODB.interfaces import IConnection

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.contenttypes.presentation.lesson import CONSTRAINT_ANNOTATION_KEY
from nti.contenttypes.presentation.lesson import LessonConstraintContainer

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
        registry = component.getSiteManager()
        connection = IConnection(registry)
        for name, lesson in list(component.getUtilitiesFor(INTILessonOverview)):
            if name in seen:
                continue
            seen.add(name)
            try:
                annotations = lesson.__annotations__
                old_constraints = annotations[CONSTRAINT_ANNOTATION_KEY]
                del annotations[CONSTRAINT_ANNOTATION_KEY]

                container = LessonConstraintContainer()
                connection.add(container)
                annotations[CONSTRAINT_ANNOTATION_KEY] = container
                container.__parent__ = lesson
                container.extend(old_constraints.values())

                old_constraints.__parent__ = None
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
    Evolve to generation 44 by changing the lesson constraint storage
    """
    do_evolve(context)
