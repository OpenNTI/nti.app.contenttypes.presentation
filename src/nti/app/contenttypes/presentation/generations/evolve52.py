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

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.event import notify

from zope.lifecycleevent import ObjectModifiedEvent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.externalization.interfaces import StandardExternalFields

from nti.site.hostpolicy import get_all_host_sites

NTIID = StandardExternalFields.NTIID

logger = __import__('logging').getLogger(__name__)

generation = 52


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


def fix_assessment_refs(current_site, seen):
    result = 0
    registry = current_site.getSiteManager()
    for name, item in list(registry.getUtilitiesFor(INTIAssessmentRef)):
        if name in seen:
            continue
        seen.add(name)

        try:
            if getattr(item, '__name__', '') == item.ntiid:
                continue
        except AttributeError:
            # Alpha data issue?
            logger.info('Invalid registered type (%s) (name=%s)', item, name)
            continue
        course = ICourseInstance(item, None)
        container = IPresentationAssetContainer(course, None)
        if container is not None:
            logger.info('Updating asset container mapping (%s) (%s)',
                        item.__name__, item.ntiid)
            container.pop(item.__name__, None)
            container.pop(item.target, None)
            container.pop(item.ntiid, None)
            container[item.ntiid] = item
        notify(ObjectModifiedEvent(item))
        result += 1
    return result


def do_evolve(context, generation=generation):
    setHooks()
    conn = context.connection
    root = conn.root()
    dataserver_folder = root['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = dataserver_folder
    component.provideUtility(mock_ds, IDataserver)

    with site(dataserver_folder):
        assert component.getSiteManager() == dataserver_folder.getSiteManager(), \
               "Hooks not installed?"

        result = 0
        seen = set()
        logger.info('Evolution %s started.', generation)
        for current_site in get_all_host_sites():
            with site(current_site):
                result += fix_assessment_refs(current_site, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done. %s item(s) processed',
                generation, result)


def evolve(context):
    """
    Evolve to 52 by making sure we update presentation asset container keys
    for the assessment refs we fixed in 51.
    """
    do_evolve(context, generation)
