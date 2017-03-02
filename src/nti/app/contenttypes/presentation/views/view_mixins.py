#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import hashlib

from nti.appserver.pyramid_authorization import has_permission

from nti.coremetadata.interfaces import IPublishable

from nti.dataserver import authorization as nauth


def hexdigest(data, hasher=None):
    hasher = hashlib.sha256() if hasher is None else hasher
    hasher.update(data)
    result = hasher.hexdigest()
    return result


class PublishVisibilityMixin(object):

    def _is_visible(self, item):
        """
        Define whether this possibly publishable object is visible to the
        remote user.
        """
        return (   not IPublishable.providedBy(item)
                or item.is_published()
                or has_permission(nauth.ACT_CONTENT_EDIT, item, self.request))
