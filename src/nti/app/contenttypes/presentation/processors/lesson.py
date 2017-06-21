#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import uuid

from zope import component
from zope import interface

from pyramid import httpexceptions as hexc

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.externalization.error import raise_json_error

from nti.app.contenttypes.presentation.processors.asset import handle_asset

from nti.app.contenttypes.presentation.processors.mixins import BaseAssetProcessor

from nti.app.contenttypes.presentation.processors.mixins import canonicalize
from nti.app.contenttypes.presentation.processors.mixins import check_exists
from nti.app.contenttypes.presentation.processors.mixins import get_context_registry

from nti.contenttypes.presentation.interfaces import INTILessonOverview


def handle_lesson_overview(lesson, context, creator, request=None):
    registry = get_context_registry(context)
    handle_asset(lesson, context, creator, request)
    # in case new NTIIDs are created
    extra = str(uuid.uuid4()).split('-')[0].upper()
    # Make sure we validate before canonicalize.
    for item in lesson.Items or ():
        # TODO: Why is this check here
        check_exists(item, registry, request, extra)
    # have unique copies of lesson groups
    canonicalize(lesson.Items, creator,
                 registry=registry,
                 base=lesson.ntiid)
    # process lesson groups
    for group in lesson or ():
        if      group.__parent__ is not None \
            and group.__parent__ != lesson:
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Overview group has been used by another lesson.'),
                                 'data': group.ntiid
                             },
                             None)
        # take ownership
        group.__parent__ = lesson
        processor = IPresentationAssetProcessor(group)
        processor.handle(group, context, creator, request)


@component.adapter(INTILessonOverview)
@interface.implementer(IPresentationAssetProcessor)
class LessonOverviewProcessor(BaseAssetProcessor):

    def handle(self, item, context, creator=None, request=None):

        item = self.asset if item is None else item
        return handle_lesson_overview(item, context, creator, request)
