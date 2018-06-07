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

from zope.intid.interfaces import IIntIds

from zope.lifecycleevent import ObjectModifiedEvent

from nti.app.contenttypes.presentation.utils.asset import registry_by_name
from nti.app.contenttypes.presentation.utils.asset import get_component_site_name

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation import interface_of_asset

from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

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

generation = 53


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


def reregister_asset(asset, registry, provided):
    if registry is None:
        logger.info('Asset without lineage/registry (%s)', asset.ntiid)
        return
    logger.info('[%s] Fixing asset (%s) (target=%s) (user_created=%s)',
                registry.__name__,
                asset.ntiid,
                asset.target,
                IUserCreatedAsset.providedBy(asset))
    unregisterUtility(registry, provided=provided, name=asset.target)
    registerUtility(registry, asset, provided, name=asset.ntiid)


def update_interfaces(item):
    user = item.creator
    if not IUser.providedBy(user):
        user = User.get_user(user)
    if user is None:
        interface.noLongerProvides(item, IUserCreatedAsset)


def process_asset(item, container, group):
    provided = interface_of_asset(item)
    registry = get_registry(item, provided)
    if registry is None and item.__parent__ is None:
        item.__parent__ = group
        registry = get_registry(item, provided)
    registered_item = registry.queryUtility(INTIAssessmentRef,
                                            name=item.ntiid)
    if registered_item == component:
        # Unregister zope component registered as item.ntiid (alpha)
        # and re-register actual assessment ref
        logger.info('Unregistered zope component (%s)', item.ntiid)
        unregisterUtility(registry, provided=provided, name=item.ntiid)
        registerUtility(registry, item, provided, name=item.ntiid)

    if item.ntiid == item.target:
        # Regenerate ntiid
        old_ntiid = item.ntiid
        delattr(item, 'ntiid')
        assert item.ntiid is not None
        update_interfaces(item)
        reregister_asset(item, registry, provided)
        # Update container mapping
        if container is not None:
            logger.info('Updating asset container mapping (%s)',
                        item.ntiid)
            container.pop(item.target, None)
            container.pop(old_ntiid, None)
            container.pop(item.ntiid, None)
            container.append(item)
        notify(ObjectModifiedEvent(item))


def process_course(course):
    course_container = IPresentationAssetContainer(course)
    def _recur(node):
        lesson = INTILessonOverview(node, None)
        if lesson is not None:
            for group in lesson or ():
                for item in group or ():
                    if INTIAssessmentRef.providedBy(item):
                        process_asset(item, course_container, group)
        for child in node.values():
            _recur(child)
    _recur(course.Outline)


def _process_site(current_site, intids, seen):
    with site(current_site):
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is None or catalog.isEmpty():
            return
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            process_course(course)


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

        seen = set()
        lsm = dataserver_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)
        logger.info('Evolution %s started.', generation)
        for current_site in get_all_host_sites():
            _process_site(current_site, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done', generation)


def evolve(context):
    """
    Evolve to 53 by making sure assessment ref ntiids do not equal the
    target ntiid.
    """
    do_evolve(context, generation)
