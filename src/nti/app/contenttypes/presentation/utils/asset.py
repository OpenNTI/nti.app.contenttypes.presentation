#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import time
import uuid

from zope import component
from zope import lifecycleevent

from zope.annotation.interfaces import IAnnotations

from zope.component.hooks import getSite

from zope.event import notify

from zope.interface.interface import InterfaceClass

from zope.location.interfaces import ILocation

from zope.location.location import locate

from ZODB.interfaces import IConnection

from nti.app.contentfolder.resources import is_internal_file_link
from nti.app.contentfolder.resources import get_file_from_external_link

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.base._compat import text_

from nti.base.interfaces import IFile

from nti.coremetadata.interfaces import SYSTEM_USER_NAME

from nti.contentlibrary.indexed_data import get_site_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import NTI
from nti.contenttypes.presentation import interface_of_asset

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTIDocketAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTICourseOverviewSpacer
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset
from nti.contenttypes.presentation.interfaces import WillRemovePresentationAssetEvent

from nti.contenttypes.presentation.lesson import NTILessonOverView

from nti.intid.common import addIntId

from nti.namedfile.file import safe_filename

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import make_specific_safe

from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.ntiids.oids import to_external_ntiid_oid

from nti.site.hostpolicy import get_host_site

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

from nti.zodb.containers import time_to_64bit_int

NOT_ALLOWED_IN_REGISTRY_REFERENCES = (IAssetRef, INTICourseOverviewSpacer)


def allowed_in_registry(provided):
    for interface in NOT_ALLOWED_IN_REGISTRY_REFERENCES:
        if provided is not None and provided.isOrExtends(interface):
            return False
    return True


def get_db_connection(registry=None):
    registry = registry if registry is not None else component.getSiteManager()
    return IConnection(registry, None)
db_connection = get_db_connection


def add_2_connection(item, registry=None, connection=None):
    connection = db_connection(registry) if connection is None else connection
    if connection is not None and getattr(item, '_p_jar', None) is None:
        connection.add(item)
    return getattr(item, '_p_jar', None) is not None


def intid_register(item, registry=None, connection=None, event=True):
    if add_2_connection(item, registry, connection):
        if event:
            lifecycleevent.added(item)
        else:
            addIntId(item)
        return True
    return False


def get_registry_by_name(name):
    folder = get_host_site(name, safe=True)
    return folder.getSiteManager() if folder is not None else None
registry_by_name = get_registry_by_name


def get_component_site(context, provided=None, name=None):
    result = None
    folder = IHostPolicyFolder(context, None)
    if folder is None:
        name = name or context.ntiid
        provided = provided or interface_of_asset(context)
        sites_names = get_component_hierarchy_names()
        for idx in range(len(sites_names) - 1, -1, -1):  # higher sites first
            folder = get_host_site(sites_names[idx])
            registry = folder.getSiteManager()
            if registry.queryUtility(provided, name=name) == context:
                result = folder
                break
    else:
        result = folder
    return result


def get_component_site_name(context, provided=None, name=None):
    site = get_component_site(context, provided, name)
    return site.__name__ if site is not None else None


def get_component_registry(context, provided=None, name=None):
    site = get_component_site(context, provided, name)
    if site is not None:
        return site.getSiteManager()
    return get_site_registry()


def notify_removed(item):
    lifecycleevent.removed(item)
    if ILocation.providedBy(item):
        locate(item, None, None)


def get_asset_registry(item, provided=None, name=None, registry=None):
    if registry is None:
        registry = get_component_registry(item, provided, name=name)
    return registry


def remove_asset(item, registry=None, catalog=None, name=None, event=True):
    if event:
        # This removes from container
        notify(WillRemovePresentationAssetEvent(item))
    # remove utility
    name = item.ntiid or name
    provided = interface_of_asset(item)
    registry = get_asset_registry(item, provided, name, registry=registry)
    try:
        if name and not unregisterUtility(registry, provided=provided, name=name):
            logger.warn("Could not unregister %s,%s from %s",
                        provided.__name__, name, registry.__parent__)
    except KeyError:
        logger.warn("Asset %s,%s not in registry %s",
                    provided.__name__, name, registry.__parent__)
    # unindex
    catalog = get_library_catalog() if catalog is None else catalog
    catalog.unindex(item)
    # broadcast removed
    notify_removed(item)  # remove intid
    return item


def remove_mediaroll(item, registry=None, catalog=None, name=None, event=True, remove_video_refs=True):
    removed = set()
    if isinstance(item, six.string_types):
        item = component.queryUtility(INTIMediaRoll, name=item)
    if item is None:
        return
    name = item.ntiid or name
    registry = get_asset_registry(item, INTIMediaRoll, name, registry)
    catalog = get_library_catalog() if catalog is None else catalog
    if remove_video_refs:
        # remove mediarefs first
        for media in tuple(item):  # mutating
            removed.add(remove_asset(media, registry, catalog, event=event))
    # remove roll
    removed.add(remove_asset(item, registry, catalog, name=name, event=event))
    removed.discard(None)
    return tuple(removed)


def remove_group(group, registry=None, catalog=None, name=None, event=True):
    if isinstance(group, six.string_types):
        group = component.queryUtility(INTICourseOverviewGroup, name=group)
    if group is None:
        return
    removed = set()
    name = group.ntiid or name
    registry = get_asset_registry(group, INTICourseOverviewGroup,
                                  name, registry=registry)
    catalog = get_library_catalog() if catalog is None else catalog
    # remove items first
    for item in tuple(group):  # mutating
        if INTIMediaRoll.providedBy(item):
            removed.update(
                remove_mediaroll(item, registry, catalog, event=event)
            )
        elif not IContentBackedPresentationAsset.providedBy(item):
            removed.add(remove_asset(item, registry, catalog, event=event))
    # remove groups
    removed.add(remove_asset(group, registry, catalog, name=name, event=event))
    removed.discard(None)
    return tuple(removed)


def remove_lesson(item, registry=None, catalog=None, name=None, event=True):
    if isinstance(item, six.string_types):
        item = component.queryUtility(INTILessonOverview, name=item)
    if item is None:
        return ()
    removed = set()
    name = item.ntiid or name
    registry = get_asset_registry(item, INTILessonOverview,
                                  name, registry=registry)
    catalog = get_library_catalog() if catalog is None else catalog
    # remove groups first
    for group in tuple(item):  # mutating
        removed.update(
            remove_group(group, registry, catalog, event=event)
        )
    # remove asset
    removed.add(remove_asset(item, registry, catalog, name=name, event=event))
    removed.discard(None)
    return tuple(removed)


def remove_presentation_asset(item, registry=None, catalog=None, name=None, event=True):
    if INTILessonOverview.providedBy(item):
        result = remove_lesson(item, registry, catalog, name=name, event=event)
    elif INTICourseOverviewGroup.providedBy(item):
        result = remove_group(item, registry, catalog, name=name, event=event)
    elif INTIMediaRoll.providedBy(item):
        result = remove_mediaroll(item, registry, catalog,
                                  name=name, event=event)
    else:
        result = remove_asset(item, registry, catalog, name=name, event=event)
    return result


def get_site_provider():
    policy = component.queryUtility(ISitePolicyUserEventListener)
    result = getattr(policy, 'PROVIDER', None)
    if not result:
        annontations = IAnnotations(getSite(), {})
        result = annontations.get('PROVIDER')
    return result or NTI


def make_asset_ntiid(nttype, base=None, extra=None, now=None):
    if type(nttype) == InterfaceClass:
        nttype = nttype.__name__[1:]

    provider = get_provider(base) if base else get_site_provider()
    current_time = time_to_64bit_int(time.time() if now is None else now)
    specific_base = u'%s.%s' % (SYSTEM_USER_NAME, current_time)
    if extra:
        specific_base = specific_base + u".%s" % extra
    specific = make_specific_safe(specific_base)

    ntiid = make_ntiid(nttype=nttype,
                       base=base,
                       provider=provider,
                       specific=specific)
    return ntiid


def get_course_for_node(node):
    return find_interface(node, ICourseInstance, strict=False)
course_for_node = get_course_for_node


def create_lesson_4_node(node, ntiid=None, registry=None, catalog=None, sites=None):
    creator = getattr(node, 'creator', None)
    creator = getattr(creator, 'username', creator)
    if not ntiid:
        extra = str(uuid.uuid4().get_time_low())
        ntiid = make_asset_ntiid(nttype=INTILessonOverview,
                                 base=node.ntiid,
                                 extra=extra)

    result = NTILessonOverView()
    result.__parent__ = node  # lineage
    result.ntiid = ntiid
    result.creator = creator
    result.title = getattr(node, 'title', None)

    # XXX If there is no lesson set it to the overview
    if hasattr(node, 'ContentNTIID') and not node.ContentNTIID:
        node.ContentNTIID = ntiid

    # XXX: set lesson overview ntiid
    # At his point is very likely that LessonOverviewNTIID,
    # ContentNTIID are simply alias fields. All of them
    # are kept so long as we have manual sync and BWC
    node.LessonOverviewNTIID = ntiid

    # XXX: if registry is specified register the new node
    if registry is not None:
        # add to course container
        course = get_course_for_node(node)
        if course is not None:
            entry = ICourseCatalogEntry(course)
            container = IPresentationAssetContainer(course)
            ntiids = (entry.ntiid,)  # container ntiid
            container[ntiid] = result  # add to container
        else:
            ntiids = None

        # register lesson
        intid_register(result, registry=registry, event=False)
        registerUtility(registry,
                        result,
                        provided=INTILessonOverview,
                        name=ntiid)

        # XXX: set the src field to be unique for indexing see
        # MediaByOutlineNode
        if not getattr(node, 'src', None):
            oid = to_external_ntiid_oid(result)
            node.src = safe_filename(oid) + '.json'  # make it a json file

        # index
        catalog = get_library_catalog() if catalog is None else catalog
        catalog.index(result, container_ntiids=ntiids,
                      namespace=node.src, sites=sites)

    # lesson is ready
    return result


def check_docket_targets(asset):
    if INTIDocketAsset.providedBy(asset) and not asset.target:
        href = asset.href
        if IFile.providedBy(href):
            asset.target = to_external_ntiid_oid(href)
            asset_type = getattr(href, 'contentType', None) or asset.type
            asset.type = text_(asset_type) if asset_type else None
        elif is_valid_ntiid_string(href):
            asset.target = href
        elif is_internal_file_link(href):
            ext = get_file_from_external_link(href)
            asset.target = to_external_ntiid_oid(ext)
            asset_type = getattr(ext, 'contentType', None) or asset.type
            asset.type = text_(asset_type) if asset_type else None
        return True
    return False
check_related_work_target = check_docket_targets  # BWC
