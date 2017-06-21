#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 35

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from nti.contenttypes.presentation.interfaces import INTIDocketAsset
from nti.contenttypes.presentation.interfaces import IUserCreatedAsset

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.users import User

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


def _fix_refs(current_site, seen):
    result = 0
    registry = current_site.getSiteManager()
    for name, item in list(registry.getUtilitiesFor(INTIDocketAsset)):
        if name in seen:
            continue
        seen.add(name)
        creator = getattr(item, 'creator', None)
        user = User.get_user(creator) if creator else None
        if user is not None:
            interface.alsoProvides(item, IUserCreatedAsset)
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
                result += _fix_refs(current_site, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done. %s item(s) marked',
                generation, result)


def evolve(context):
    """
    Evolve to 35 by marking user created assets with interface
    """
    do_evolve(context, generation)
