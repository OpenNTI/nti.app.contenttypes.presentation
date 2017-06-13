#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import uuid
import hashlib
from collections import Mapping

from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from nti.app.renderers.interfaces import INoHrefInResponse

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.externalization.error import raise_json_error

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.presentation import ALL_MEDIA_ROLL_MIME_TYPES
from nti.contenttypes.presentation import LESSON_OVERVIEW_MIME_TYPES
from nti.contenttypes.presentation import COURSE_OVERVIEW_GROUP_MIME_TYPES

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE

#: Max title length preflight routines
MAX_TITLE_LENGTH = 300


def hexdigest(data, hasher=None):
    hasher = hashlib.sha256() if hasher is None else hasher
    hasher.update(data)
    result = hasher.hexdigest()
    return result


def href_safe_to_external_object(obj):
    result = to_external_object(obj)
    interface.alsoProvides(result, INoHrefInResponse)
    return result


def validate_input(external_value, request=None):
    request = request or get_current_request()
    # Normally, we'd let our defined schema enforce limits,
    # but old, unreasonable content makes us enforce some
    # limits here, through the user API.
    for attr in ('title', 'Title', 'label', 'Label'):
        value = external_value.get(attr)
        if value and len(value) > MAX_TITLE_LENGTH:
            # Mapping to what we do in nti.schema.field.
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'provided_size': len(value),
                                 'max_size': MAX_TITLE_LENGTH,
                                 'message': _(u'${field} is too long. ${max_size} character limit.',
                                              mapping={'field': attr.capitalize(),
                                                       'max_size': MAX_TITLE_LENGTH}),
                                 'code': 'TooLong',
                                 'field': attr.capitalize()
                             },
                             None)


def preflight_mediaroll(external_value, request=None):
    request = request or get_current_request()
    if not isinstance(external_value, Mapping):
        return external_value
    items = external_value.get(ITEMS)
    validate_input(external_value, request)
    for idx, item in enumerate(items or ()):
        if isinstance(item, six.string_types):
            item = items[idx] = {'ntiid': item}
        if isinstance(item, Mapping) and MIMETYPE not in item:
            ntiid = item.get('ntiid') or item.get(NTIID)
            __traceback_info__ = ntiid
            if not ntiid:
                raise_json_error(request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                    'message':  _(u'Missing media roll item NTIID.'),
                                    'field': 'ntiid'
                                 },
                                 None)
            resolved = find_object_with_ntiid(ntiid)
            if resolved is None:
                raise_json_error(request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                    'message':  _(u'Missing media roll item.'),
                                 },
                                 None)
            if (   INTIMedia.providedBy(resolved) 
                or INTIMediaRef.providedBy(resolved)):
                item[MIMETYPE] = resolved.mimeType
            else:
                raise_json_error(request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                    'message':  _(u'Invalid media roll item.'),
                                 },
                                 None)
    # If they're editing a field, make sure we have a mimetype
    # so our pre-hooks fire.
    if MIMETYPE not in external_value:
        external_value[MIMETYPE] = "application/vnd.nextthought.ntivideoroll"
    return external_value


def preflight_overview_group(external_value, request=None):
    request = request or get_current_request()
    if not isinstance(external_value, Mapping):
        return external_value
    validate_input(external_value, request)
    items = external_value.get(ITEMS)
    for idx, item in enumerate(items or ()):
        if isinstance(item, six.string_types):
            item = items[idx] = {'ntiid': item}
        if isinstance(item, Mapping) and MIMETYPE not in item:
            ntiid = item.get('ntiid') or item.get(NTIID)
            __traceback_info__ = ntiid
            if not ntiid:
                raise_json_error(request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                    'message':  _(u'Missing overview group item NTIID.'),
                                    'field': 'ntiid'
                                 },
                                 None)
            resolved = find_object_with_ntiid(ntiid)
            if resolved is None:
                raise_json_error(request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                    'message':  _(u'Missing overview group item.'),
                                    'field': 'ntiid'
                                 },
                                 None)
            if not IGroupOverViewable.providedBy(resolved):
                logger.warn("Coercing %s,%s into overview group",
                            resolved.mimeType, ntiid)
            item[MIMETYPE] = resolved.mimeType
        else:
            preflight_input(item)
    return external_value


def preflight_lesson_overview(external_value, request=None):
    request = request or get_current_request()
    if not isinstance(external_value, Mapping):
        return external_value
    validate_input(external_value, request)
    items = external_value.get(ITEMS)
    for item in items or ():
        preflight_overview_group(item, request)
    return external_value


def preflight_input(external_value, request=None):
    request = request or get_current_request()
    if not isinstance(external_value, Mapping):
        return external_value
    mimeType = external_value.get(MIMETYPE) or external_value.get('mimeType')
    if mimeType in ALL_MEDIA_ROLL_MIME_TYPES:
        return preflight_mediaroll(external_value, request)
    elif mimeType in COURSE_OVERVIEW_GROUP_MIME_TYPES:
        return preflight_overview_group(external_value, request)
    elif mimeType in LESSON_OVERVIEW_MIME_TYPES:
        return preflight_lesson_overview(external_value, request)
    validate_input(external_value, request)
    return external_value


class PresentationAssetMixin(object):

    @Lazy
    def _site_name(self):
        return getSite().__name__
    site_name = _site_name

    @Lazy
    def _catalog(self):
        return get_library_catalog()
    catalog = _catalog

    @Lazy
    def _extra(self):
        return str(uuid.uuid4()).split('-')[0].upper()
    extra = _extra

    @Lazy
    def _registry(self):
        return getSite().getSiteManager()
    registry = _registry


class PublishVisibilityMixin(object):

    def _is_visible(self, item):
        """
        Define whether this possibly publishable object is visible to the
        remote user.
        """
        return (   not IPublishable.providedBy(item)
                or item.is_published()
                or has_permission(nauth.ACT_CONTENT_EDIT, item, self.request))
