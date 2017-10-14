#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import ILocation

from nti.app.contenttypes.presentation import MessageFactory

from nti.app.contenttypes.presentation import VIEW_ASSETS
from nti.app.contenttypes.presentation import VIEW_NODE_MOVE
from nti.app.contenttypes.presentation import VIEW_TRANSCRIPTS
from nti.app.contenttypes.presentation import VIEW_NODE_CONTENTS
from nti.app.contenttypes.presentation import VIEW_OVERVIEW_CONTENT
from nti.app.contenttypes.presentation import VIEW_OVERVIEW_SUMMARY
from nti.app.contenttypes.presentation import VIEW_ORDERED_CONTENTS

from nti.app.products.courseware.utils import PreviewCourseAccessPredicateDecorator

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.common.string import is_true

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields

from nti.links.links import Link

from nti.publishing.interfaces import IPublishable

LINKS = StandardExternalFields.LINKS

LEGACY_UAS_20 = ("NTIFoundation DataLoader NextThought/1.0",
                 "NTIFoundation DataLoader NextThought/1.1",
                 "NTIFoundation DataLoader NextThought/1.1.1",
                 "NTIFoundation DataLoader NextThought/1.2.")

LEGACY_UAS_40 = LEGACY_UAS_20 + \
                ("NTIFoundation DataLoader NextThought/1.3.",
                 "NTIFoundation DataLoader NextThought/1.4.0")

logger = __import__('logging').getLogger(__name__)


def is_legacy_uas(request, legacy_uas=LEGACY_UAS_40):
    ua = request.environ.get('HTTP_USER_AGENT', '')
    if not ua:
        return False
    for lua in legacy_uas:
        if ua.startswith(lua):
            return True
    return False


def _is_visible(item, request, show_unpublished=True):
    return not IPublishable.providedBy(item) \
        or item.is_published() \
        or (show_unpublished and has_permission(ACT_CONTENT_EDIT, item, request))


def get_omit_published(request):
    omit_unpublished = request.params.get('omit_unpublished', False)
    try:
        omit_unpublished = is_true(omit_unpublished)
    except ValueError:
        omit_unpublished = False
    return omit_unpublished


def can_view_publishable(context, request):
    """
    Defines whether the given publishable object is visible to the end-user.
    If an `omit_unpublished` param exists on the request, the unpublished
    item will be hidden from editors as well.
    """
    show_unpublished = not get_omit_published(request)
    return _is_visible(context, request, show_unpublished=show_unpublished)


class _AbstractMoveLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    @Lazy
    def _acl_decoration(self):
        return getattr(self.request, 'acl_decoration', True)

    def _predicate(self, context, unused_result):
        return (    self._acl_decoration
                and self._is_authenticated
                and has_permission(ACT_CONTENT_EDIT, context, self.request))

    def _do_decorate_external(self, context, result):
        links = result.setdefault(LINKS, [])
        link = Link(context, rel=VIEW_NODE_MOVE, elements=(VIEW_NODE_MOVE,))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        links.append(link)
