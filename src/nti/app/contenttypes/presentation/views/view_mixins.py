#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import uuid
import hashlib

from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from nti.app.renderers.interfaces import INoHrefInResponse

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import to_external_object

from nti.publishing.interfaces import IPublishable


def hexdigest(data, hasher=None):
    hasher = hashlib.sha256() if hasher is None else hasher
    hasher.update(data)
    result = hasher.hexdigest()
    return result


def href_safe_to_external_object(obj):
    result = to_external_object(obj)
    interface.alsoProvides(result, INoHrefInResponse)
    return result


class PresentationAssetMixin(object):

    @Lazy
    def site_name(self):
        return getSite().__name__
    _site_name = site_name

    @Lazy
    def catalog(self):
        return get_library_catalog()
    _catalog = catalog

    @Lazy
    def extra(self):
        return str(uuid.uuid4()).split('-')[0].upper()
    _extra = extra

    @Lazy
    def registry(self):
        return getSite().getSiteManager()
    _registry = registry


class PublishVisibilityMixin(object):

    def _is_visible(self, item):
        """
        Define whether this possibly publishable object is visible to the
        remote user.
        """
        return (   not IPublishable.providedBy(item)
                or item.is_published()
                or has_permission(nauth.ACT_CONTENT_EDIT, item, self.request))
