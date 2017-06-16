#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urlparse import urlparse

from zope import interface
from zope import component
from zope import lifecycleevent

from pyramid.threadlocal import get_current_request

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.processors.mixins import hexdigest
from nti.app.contenttypes.presentation.processors.mixins import get_content_file

from nti.app.contenttypes.presentation.processors.package import handle_package_asset

from nti.app.products.courseware.resources.utils import get_course_filer
from nti.app.products.courseware.resources.utils import is_internal_file_link
from nti.app.products.courseware.resources.utils import to_external_file_link

from nti.base._compat import text_

from nti.contentlibrary.interfaces import IContentUnit

from nti.contenttypes.presentation.interfaces import INTIDocketAsset
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.externalization.oids import to_external_ntiid_oid

from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid


def handle_docket_asset(item, context=None, creator=None):
    # check for contentfiles in icon and href
    for name in ('href', 'icon'):
        name = str(name)
        value = getattr(item, name, None)
        content_file = get_content_file(value)
        if content_file is None:
            continue
        external = to_external_file_link(content_file)
        setattr(item, name, external)
        content_file.add_association(item)
        lifecycleevent.modified(content_file)
        if name == 'href':  # update target and type
            item.target = to_external_ntiid_oid(item)  # NTIID
            if INTIRelatedWorkRef.providedBy(item):
                item.type = text_(content_file.contentType)


def handle_related_work(item, context, creator=None, request=None):
    request = request or get_current_request()
    handle_package_asset(item, context, creator)
    # capture updated/previous data
    ntiid, href = item.target, item.href
    contentType = item.type or u'application/octet-stream'  # default
    # if client has uploaded a file, capture contentType and target ntiid
    if      request.POST \
        and 'href' in request.POST \
        and is_internal_file_link(href):
        filer = get_course_filer(context)
        named = filer.get(href) if href else None
        if named is not None:
            ntiid = to_external_ntiid_oid(named)
            contentType = text_(named.contentType or '') or contentType
    # If we do not have a target, and we have a ContentUnit href, use it.
    if ntiid is None and is_valid_ntiid_string(item.href):
        href_obj = find_object_with_ntiid(item.href)
        if href_obj is not None and IContentUnit.providedBy(href_obj):
            ntiid = item.href
    # parse href
    parsed = urlparse(href) if href else None
    # full url
    if ntiid is None and parsed is not None and (parsed.scheme or parsed.netloc):
        ntiid = make_ntiid(nttype=TYPE_UUID,
                           provider='NTI',
                           specific=hexdigest(href.lower()))
    # replace if needed
    if item.target != ntiid:
        item.target = ntiid
    if item.type != contentType:
        item.type = contentType
    # handle common docket
    handle_docket_asset(item, context, creator)


@component.adapter(INTIDocketAsset)
@interface.implementer(IPresentationAssetProcessor)
class DocketAssetProcessor(object):

    __slots__ = ()

    def handle(self, item, context, creator=None, request=None):
        handle_package_asset(item, context, creator)
        return handle_docket_asset(item, context, creator)


@component.adapter(INTIRelatedWorkRef)
@interface.implementer(IPresentationAssetProcessor)
class RelatedWorkfRefProcessor(object):

    __slots__ = ()

    def handle(self, item, context, creator=None, request=None):
        return handle_related_work(item, context, creator, request)
