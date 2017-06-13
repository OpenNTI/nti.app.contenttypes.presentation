#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.utils import resolve_discussion_course_bundle

from nti.app.contenttypes.presentation.views.view_mixins import PublishVisibilityMixin
from nti.app.contenttypes.presentation.views.view_mixins import href_safe_to_external_object

from nti.app.products.courseware import VIEW_RECURSIVE_AUDIT_LOG
from nti.app.products.courseware import VIEW_RECURSIVE_TX_HISTORY

from nti.app.products.courseware.views.view_mixins import AbstractRecursiveTransactionHistoryView

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.dataserver import authorization as nauth


@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_READ,
               request_method='GET')
class PresentationAssetGetView(GenericGetView, PublishVisibilityMixin):

    def __call__(self):
        accept = self.request.headers.get(b'Accept') or u''
        if accept == 'application/vnd.nextthought.pageinfo+json':
            raise hexc.HTTPNotAcceptable()
        if not self._is_visible(self.context):
            raise hexc.HTTPForbidden(_("Item not visible."))
        result = GenericGetView.__call__(self)
        return result


@view_config(context=INTITimeline)
@view_config(context=INTIRelatedWorkRef)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_READ,
               request_method='GET')
class NoHrefAssetGetView(PresentationAssetGetView):

    def __call__(self):
        result = PresentationAssetGetView.__call__(self)
        result = href_safe_to_external_object(result)
        return result


@view_config(context=INTIDiscussionRef)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_READ,
               request_method='GET')
class DiscussionRefGetView(AbstractAuthenticatedView, PublishVisibilityMixin):

    def __call__(self):
        accept = self.request.headers.get('Accept') or ''
        if accept == 'application/vnd.nextthought.discussionref':
            if not self._is_visible(self.context):
                raise hexc.HTTPForbidden(_("Item not visible."))
            return self.context
        elif self.context.isCourseBundle():
            course = ICourseInstance(self.context, None)
            resolved = resolve_discussion_course_bundle(user=self.remoteUser,
                                                        item=self.context,
                                                        context=course)
            if resolved is not None:
                cdiss, topic = resolved
                logger.debug('%s resolved to %s', self.context.id, cdiss)
                return topic
            else:
                raise hexc.HTTPNotFound(_("Topic not found."))
        else:
            raise hexc.HTTPNotAcceptable()


@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_READ,
               request_method='GET',
               name="schema")
class PresentationAssetSchemaView(AbstractAuthenticatedView):

    def __call__(self):
        result = self.context.schema()
        return result


@view_config(name=VIEW_RECURSIVE_AUDIT_LOG)
@view_config(name=VIEW_RECURSIVE_TX_HISTORY)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_CONTENT_EDIT,
               context=INTILessonOverview)
class RecursiveCourseTransactionHistoryView(AbstractRecursiveTransactionHistoryView):
    """
    A batched view to get all edits that have occurred in the lesson, recursively.
    """

    def _get_items(self):
        result = []
        self._accum_lesson_transactions(self.context, result)
        return result
