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

from nti.app.contenttypes.presentation.utils.asset import registry_by_name
from nti.app.contenttypes.presentation.utils.asset import get_component_site_name

from nti.contenttypes.presentation import interface_of_asset

from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import INTIAssessmentRef

from nti.coremetadata.interfaces import IUser

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.users import User

from nti.externalization.interfaces import StandardExternalFields

from nti.site.hostpolicy import get_all_host_sites

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

NTIID = StandardExternalFields.NTIID

logger = __import__('logging').getLogger(__name__)

generation = 51


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


def get_registry(asset, provided):
    # XXX: use correct registration site
    site_name = get_component_site_name(asset,
                                        provided,
                                        name=asset.ntiid)
    return registry_by_name(site_name)


def reregister_asset(asset):
    provided = interface_of_asset(asset)
    registry = get_registry(asset, provided)
    if registry is None:
        logger.info('Asset without lineage/registry (%s)', asset.ntiid)
        return
    logger.info('[%s] Fixing asset (%s) (target=%s) (user_created=%s)',
                registry.__name__,
                asset.ntiid,
                asset.target,
                IUserCreatedAsset.providedBy(asset))
    unregisterUtility(registry, provided=provided, name=asset.target)
    registerUtility(registry, component, provided, name=asset.ntiid)


def update_interfaces(item):
    user = item.creator
    if not IUser.providedBy(user):
        user = User.get_user(user)
    if user is None:
        interface.noLongerProvides(item, IUserCreatedAsset)


def fix_assessment_refs(current_site, seen):
    result = 0
    registry = current_site.getSiteManager()
    for name, item in list(registry.getUtilitiesFor(INTIAssessmentRef)):
        if name in seen:
            continue
        seen.add(name)
        try:
            if item.ntiid != item.target:
                continue
        except AttributeError:
            # Alpha data issue?
            continue

        # Regenerate ntiid
        delattr(item, 'ntiid')
        assert item.ntiid is not None
        update_interfaces(item)
        reregister_asset(item)
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
    Evolve to 51 by making sure assessment ref ntiids do not equal the
    target ntiid.
    """
    do_evolve(context, generation)
