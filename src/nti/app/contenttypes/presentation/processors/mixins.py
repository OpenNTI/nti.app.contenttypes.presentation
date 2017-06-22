#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import hashlib

from zope import component
from zope import interface

from zope.event import notify as event_notify

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from nti.app.base.abstract_views import get_safe_source_filename

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.utils.asset import make_asset_ntiid

from nti.app.externalization.error import raise_json_error

from nti.app.products.courseware.resources.utils import get_course_filer
from nti.app.products.courseware.resources.utils import is_internal_file_link
from nti.app.products.courseware.resources.utils import get_file_from_external_link

from nti.contentfile.interfaces import IContentBaseFile

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.interfaces import PresentationAssetCreatedEvent

from nti.coremetadata.utils import current_principal

from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable

from nti.site.interfaces import IHostPolicyFolder

from nti.site.utils import registerUtility


@interface.implementer(IPresentationAssetProcessor)
class BaseAssetProcessor(object):

    def __init__(self, asset=None):
        self.asset = asset

    def handle(self, item, context, creator=None, request=None):
        raise NotImplementedError()


def hexdigest(data, hasher=None):
    hasher = hashlib.sha256() if hasher is None else hasher
    hasher.update(data)
    result = hasher.hexdigest()
    return result


def principalId():
    current_principal(True).id


def notify_created(item, principal=None, externalValue=None):
    principal = principal or principalId()  # always get a principal
    event_notify(PresentationAssetCreatedEvent(item, principal, externalValue))
    if IPublishable.providedBy(item) and item.is_published():
        item.unpublish(event=False)


def add_to_course(context, item):
    course = ICourseInstance(context, None)
    if course is not None:
        container = IPresentationAssetContainer(course, None)
        container[item.ntiid] = item


def add_to_courses(context, item):
    add_to_course(context, item)
    for subinstance in get_course_subinstances(context):
        add_to_course(subinstance, item)


def add_to_container(context, item):
    add_to_courses(context, item)


def register_utility(registry, item, provided, name=None):
    name = name or item.ntiid
    registerUtility(registry, item, provided, name=name)


def canonicalize(items, creator, base=None, registry=None):
    result = []
    registry = registry or component.getSiteManager()
    for idx, item in enumerate(items or ()):
        created = True
        provided = iface_of_asset(item)
        if not item.ntiid:
            item.ntiid = make_asset_ntiid(provided, base=base, extra=idx)
        else:
            stored = registry.queryUtility(provided, name=item.ntiid)
            if stored is not None:
                created = False
                items[idx] = stored
        if created:
            result.append(item)
            item.creator = creator
            register_utility(registry, item, provided, name=item.ntiid)
    return result


def handle_multipart(context, user, contentObject, sources, provided=None):
    filer = get_course_filer(context, user)
    provided = iface_of_asset(contentObject) if provided is None else provided
    for name, source in sources.items():
        if name in provided:
            # remove existing
            location = getattr(contentObject, name, None)
            if location and is_internal_file_link(location):
                filer.remove(location)
            # save a in a new file
            key = get_safe_source_filename(source, name)
            location = filer.save(key, source,
                                  overwrite=False,
                                  structure=True,
                                  context=contentObject)
            setattr(contentObject, name, location)


def set_creator(item, creator):
    item_byline = getattr(item, 'byline', None)
    item_creator = getattr(item, 'creator', None)
    creator = getattr(creator, 'username', creator)
    if not item_creator or item_creator == item_byline:
        item.creator = creator or principalId()


def get_ntiid(item):
    ntiid = item.ntiid
    # Return None for auto-generate NTIIDs
    if      ntiid \
        and (INTICourseOverviewGroup.providedBy(item) or IAssetRef.providedBy(item)) \
        and TYPE_UUID in get_specific(ntiid):
        ntiid = None
    return ntiid


def check_exists(item, registry, request=None, extra=None):
    ntiid = get_ntiid(item)
    provided = iface_of_asset(item)
    if ntiid and INTITimeline.providedBy(item):
        # Timelines are the only item we allow to be placed as-is (non-ref).
        pass
    elif ntiid:
        if registry.queryUtility(provided, name=ntiid):
            request = request or get_current_request()
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Asset already exists.'),
                             },
                             None)
    else:
        item.ntiid = make_asset_ntiid(provided, extra=extra)
    return item


def get_content_file(value):
    if not isinstance(value, six.string_types):
        return None
    result = None
    if is_valid_ntiid_string(value):
        result = find_object_with_ntiid(value)
    elif is_internal_file_link(value):
        result = get_file_from_external_link(value)
    if not IContentBaseFile.providedBy(result):
        result = None
    return result


def get_context_site(context):
    return IHostPolicyFolder(context, None)


def get_context_registry(context):
    site = get_context_site(context)
    return site.getSiteManager() if site is not None else None
