#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.presentation.views import VIEW_LESSON_PROGRESS
from nti.app.contenttypes.presentation.views import VIEW_LESSON_PROGRESS_STATS

from nti.app.externalization.error import raise_json_error

from nti.contentlibrary.indexed_data import get_catalog

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ICompletableItem
from nti.contenttypes.completion.interfaces import ICompletedItemContainer

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import get_course_instructors

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.dataserver.authorization import ACT_READ

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names

ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseOutlineContentNode,
             request_method='GET',
             permission=ACT_READ,
             name=VIEW_LESSON_PROGRESS)
class LessonProgressView(AbstractAuthenticatedView):
    """
    For the given content outline node, return the progress we have for the
    user on each ntiid within the content node.  This will include
    self-assessments and assignments for the course.  On return, the
    'LastModified' header will be set, allowing the client to specify the
    'If-Modified-Since' header for future requests.  A 304 will be returned
    if there is the results have not changed.
    """

    def _get_last_mod(self, progress, max_last_mod):
        """
        For progress, get the most recent date as our last modified.
        """
        result = max_last_mod

        if     not max_last_mod \
            or (    progress.last_modified
                and progress.last_modified > max_last_mod):
            result = progress.last_modified
        return result

    def _get_progress_objects(self, obj, accum):
        obj = IConcreteAsset(obj, obj)
        accum.add(obj)
        attrs_to_check = ('ntiid',)
        if INTIRelatedWorkRef.providedBy(obj):
            attrs_to_check = ('ntiid', 'href')

        for attr in attrs_to_check:
            target_ntiid = getattr(obj, attr, None)
            if target_ntiid is not None:
                target = find_object_with_ntiid(target_ntiid)
                if target is not None:
                    accum.add(target)
        try:
            for item in obj.items or ():
                self._get_progress_objects(item, accum)
        except AttributeError:
            pass

    def _get_legacy_progress_objects(self, unit, accum):
        if unit is None:
            return
        else:
            self._get_progress_objects(unit, accum)
            for ntiid in unit.embeddedContainerNTIIDs:
                obj = find_object_with_ntiid(ntiid)
                accum.add(obj)
                if hasattr(obj, 'target'):
                    target = find_object_with_ntiid(obj.target)
                    if target is not None:
                        accum.add(target)
            for child in unit.children:
                self._get_legacy_progress_objects(child, accum)

    def _get_lesson_progress_objects(self, lesson, lesson_ntiid):
        results = set()
        catalog = get_catalog()
        rs = catalog.search_objects(container_ntiids=lesson_ntiid,
                                    sites=get_component_hierarchy_names(),
                                    provided=ALL_PRESENTATION_ASSETS_INTERFACES)
        assets = tuple(rs)
        if not assets and lesson is not None:
            # If we have a lesson, iterate through lesson
            assets = tuple(lesson)
        for item in assets:
            self._get_progress_objects(item, results)
        return results

    def __call__(self):
        # - Locally, this is quick. ~1s (much less when cached) to get
        # ntiids under node; ~.05s to get empty resource set.  Bumps up to ~.3s
        # once the user starts accumulating events.
        ntiid = self.context.LessonOverviewNTIID
        course = ICourseInstance(self.context, None)
        try:
            if course is None:
                ntiid = self.context.ContentNTIID
                content_unit = find_object_with_ntiid(ntiid)
                course = ICourseInstance(content_unit)
        except TypeError:
            logger.warn('No course found for content unit; cannot return progress ',
                        ntiid)
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Cannot gather progress for course lesson."),
                                 'code': u'CourseNotFoundError'
                             },
                             None)

        if ntiid:
            lesson = find_object_with_ntiid(ntiid)
            items = self._get_lesson_progress_objects(lesson, ntiid)
        else:
            # Legacy
            items = set()
            ntiid = self.context.ContentNTIID
            lesson = find_object_with_ntiid(ntiid)
            self._get_legacy_progress_objects(lesson, items)
        items.discard(None)

        result = LocatedExternalDict()
        result[StandardExternalFields.CLASS] = 'CourseOutlineNodeProgress'
        result[StandardExternalFields.MIMETYPE] = 'application/vnd.nextthought.progresscontainer'
        result[StandardExternalFields.ITEMS] = item_dict = {}

        node_last_modified = None

        # Get progress for possible items
        for item in items or ():
            progress = component.queryMultiAdapter((self.remoteUser, item, course),
                                                   IProgress)
            if progress is not None:
                item_dict[item.ntiid] = to_external_object(progress)
                node_last_modified = self._get_last_mod(progress,
                                                        node_last_modified)

        # Setting this will enable the renderer to return a 304, if needed.
        self.request.response.last_modified = node_last_modified
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseOutlineContentNode,
             request_method='GET',
             permission=ACT_READ,
             name=VIEW_LESSON_PROGRESS_STATS)
class LessonCompletionStatisticsView(AbstractAuthenticatedView):
    """
    Fetch the completed item statistics for items in the lesson. This
    view will be widely available, so we should take care to return
    anonymous data only here.
    """

    @Lazy
    def course(self):
        return ICourseInstance(self.context, None)

    def _get_enrolled_usernames(self):
        """
        Get the enrolled non-instructor, non-editor usernames.
        """
        usernames = set(ICourseEnrollments(self.course).iter_principals())
        admins = list(get_course_instructors(self.course))
        editors = list(get_course_editors(self.course))
        admins.extend(editors)
        admin_usernames = set(getattr(x, 'username', x) for x in admins)
        return usernames - admin_usernames

    def _validate(self):
        if self.course is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Cannot gather progress without course."),
                                 'code': u'CourseNotFoundError'
                             },
                             None)

    def _get_completable_items(self, lesson):
        # TODO: Seems useful to have this logic elsewhere
        result = set()
        for group in lesson or ():
            for item in group or ():
                item = IConcreteAsset(item, item)
                if ICompletableItem.providedBy(item):
                    result.add(item)
                target = getattr(item, 'target', '')
                if target is not None:
                    target = find_object_with_ntiid(target)
                    if ICompletableItem.providedBy(target):
                        result.add(target)
        return result

    def _build_stats(self, item, completed_item_container, usernames, enrolled_count):
        completed_count = 0
        completed_date = None
        for username in usernames:
            principal_container = completed_item_container.get(username)
            if principal_container is not None:
                completed_item = principal_container.get_completed_item(item)
                if completed_item is not None:
                    completed_count += 1
                    if completed_date is None:
                        completed_date = completed_item.CompletedDate
                    else:
                        completed_date = max(completed_date,
                                             completed_item.CompletedDate)
        return {'CountCompleted': completed_count,
                'TotalUsers': enrolled_count,
                'LastCompleteDate': completed_date}

    def __call__(self):
        self._validate()
        ntiid = self.context.LessonOverviewNTIID
        lesson = find_object_with_ntiid(ntiid)
        # We might have to get smarter about this, some students may not have
        # access to all items
        usernames = self._get_enrolled_usernames()
        enrolled_count = len(usernames)
        completed_item_container = ICompletedItemContainer(self.course)
        items = self._get_completable_items(lesson)
        result = LocatedExternalDict()
        result[ITEMS] = result_dict = {}
        for item in items:
            stat_dict = self._build_stats(item,
                                          completed_item_container,
                                          usernames,
                                          enrolled_count)
            result_dict[item.ntiid] = stat_dict
        result[ITEM_COUNT] = len(items)
        result['TotalUsers'] = enrolled_count
        return result
