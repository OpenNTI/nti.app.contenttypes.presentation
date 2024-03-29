#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import ILocation

from pyramid.interfaces import IRequest

from nti.app.assessment.common.evaluations import get_course_assignments

from nti.app.assessment.decorators.assignment import AssessmentPolicyEditLinkDecorator

from nti.app.contentfolder.resources import is_internal_file_link
from nti.app.contentfolder.resources import to_external_file_link
from nti.app.contentfolder.resources import get_file_from_external_link

from nti.app.contenttypes.completion.decorators import CompletableItemDecorator

from nti.app.contenttypes.presentation.decorators import LEGACY_UAS_40
from nti.app.contenttypes.presentation.decorators import VIEW_ORDERED_CONTENTS

from nti.app.contenttypes.presentation.decorators import is_legacy_uas
from nti.app.contenttypes.presentation.decorators import get_omit_published
from nti.app.contenttypes.presentation.decorators import can_view_publishable
from nti.app.contenttypes.presentation.decorators import _AbstractMoveLinkDecorator

from nti.app.contenttypes.presentation.utils import is_item_visible

from nti.app.contenttypes.presentation.utils.course import is_video_included

from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_TOPIC
from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC

from nti.app.products.courseware.decorators import BaseRecursiveAuditLogLinkDecorator

from nti.app.products.courseware.resources.interfaces import ICourseContentFile

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment

from nti.base.interfaces import IFile

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.calendar.interfaces import ICalendar
from nti.contenttypes.calendar.interfaces import ICalendarEvent

from nti.contenttypes.completion.interfaces import ICompletableItem

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.discussions.utils import resolve_discussion_course_bundle

from nti.contenttypes.courses.interfaces import OPEN, ICourseSubInstance
from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import IN_CLASS
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ENROLLMENT_LINEAGE_MAP

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance
from nti.contenttypes.courses.interfaces import get_course_assessment_predicate_for_user

from nti.contenttypes.courses.utils import get_user_or_instructor_enrollment_record as get_any_enrollment_record
from nti.contenttypes.courses.utils import get_parent_course

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import IMediaRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTITranscript
from nti.contenttypes.presentation.interfaces import INTIQuestionRef
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICalendarEventRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.externalization import render_link

from nti.links.links import Link

from nti.ntiids.ntiids import get_type
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_provider_safe
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable

from nti.traversal.traversal import find_interface

LINKS = StandardExternalFields.LINKS
ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE
IN_CLASS_SAFE = make_provider_safe(IN_CLASS)

#: Legacy ipad key for item video rolls
COLLECTION_ITEMS = 'collectionItems'

#: Ref reading mime type
CONTENT_MIME_TYPE = 'application/vnd.nextthought.content'

logger = __import__('logging').getLogger(__name__)


@component.adapter(IPresentationAsset)
@interface.implementer(IExternalObjectDecorator)
class _PresentationAssetEditLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    @Lazy
    def _acl_decoration(self):
        result = getattr(self.request, 'acl_decoration', True)
        return result

    def _has_edit_link(self, result):
        for lnk in result.get(LINKS) or ():
            if getattr(lnk, 'rel', None) == 'edit':
                return True
        return False

    def _predicate(self, context, result):
        return  self._acl_decoration \
            and self._is_authenticated \
            and not self._has_edit_link(result) \
            and has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel='edit')
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)
        # Only API created PDF refs can change their uploaded files.
        # Import/export does not handle this case currently for
        # content backed assets.
        if      not IContentBackedPresentationAsset.providedBy(context) \
            and INTIRelatedWorkRef.providedBy(context):
            link = Link(context, rel='edit-target')
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(IPresentationAsset)
@interface.implementer(IExternalMappingDecorator)
class _PresentationAssetRequestDecorator(AbstractAuthenticatedRequestAwareDecorator):

    @Lazy
    def _acl_decoration(self):
        result = getattr(self.request, 'acl_decoration', True)
        return result

    def _predicate(self, context, unused_result):
        return  self._acl_decoration \
            and self._is_authenticated \
            and has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _do_containers(self, context, result):
        catalog = get_library_catalog()
        containers = catalog.get_containers(context)
        result['Containers'] = sorted(containers or ())

    def _do_schema_link(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    rel='schema',
                    elements=('@@schema',))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)

    def _do_decorate_external(self, context, result):
        self._do_containers(context, result)
        self._do_schema_link(context, result)


@component.adapter(INTILessonOverview)
@interface.implementer(IExternalMappingDecorator)
class _LessonMoveLinkDecorator(_AbstractMoveLinkDecorator):
    pass


@component.adapter(INTILessonOverview)
@component.adapter(INTICourseOverviewGroup)
@interface.implementer(IExternalMappingDecorator)
class _NTIAssetOrderedContentsLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    @Lazy
    def _acl_decoration(self):
        result = getattr(self.request, 'acl_decoration', True)
        return result

    def _predicate(self, context, unused_result):
        return  self._acl_decoration \
            and self._is_authenticated \
            and has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _do_decorate_external(self, context, result):
        links = result.setdefault(LINKS, [])
        link = Link(context, rel=VIEW_ORDERED_CONTENTS, elements=('contents',))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        links.append(link)


def add_ref_rel(ext_obj, ref):
    # Include a path back to the actual ref in the lesson
    _links = ext_obj.setdefault(LINKS, [])
    link = Link(ref,
                rel='Ref')
    interface.alsoProvides(link, ILocation)
    link.__name__ = ''
    link.__parent__ = ref
    link = render_link(link)
    link['RefNTIID'] = ref.ntiid
    _links.append(link)



@interface.implementer(IExternalObjectDecorator)
class _VisibleMixinDecorator(AbstractAuthenticatedRequestAwareDecorator):

    _record = None

    def record(self, context):
        if self._record is None:
            self._record = get_any_enrollment_record(context, self.remoteUser)
        return self._record

    def _predicate(self, context, result):
        if self._is_authenticated:
            result = True
        else:
            course = find_interface(context, ICourseInstance, strict=False)
            result = IAnonymouslyAccessibleCourseInstance.providedBy(course)
        return result

    def _handle_media_ref(self, items, item, idx):
        source = INTIMedia(item, None)
        if source is not None:
            items[idx] = ext_obj = to_external_object(source,
                                                      useCache=False)
            if item != source:
                add_ref_rel(ext_obj, item)
            return True
        return False

    def _allow_visible(self, context, item):
        record = self.record(context)
        result = is_item_visible(item, user=self.remoteUser,
                                 context=context, record=record)
        return result

    def _decorate_external_impl(self, context, result):
        pass

    def _do_decorate_external(self, context, result):
        try:
            __traceback_info__ = context
            self._decorate_external_impl(context, result)
        except Exception:
            logger.exception("Error while decorating asset")


@component.adapter(INTIMediaRoll)
class _NTIMediaRollDecorator(_VisibleMixinDecorator):

    @Lazy
    def is_legacy_ipad(self):
        result = is_legacy_uas(self.request, LEGACY_UAS_40)
        return result

    def _decorate_external_impl(self, context, result):
        removal = set()
        items = result[ITEMS]
        # loop through sources
        for idx, item in enumerate(context):
            if IVisible.providedBy(item) and not self._allow_visible(context, item):
                removal.add(idx)
            elif IMediaRef.providedBy(item):
                self._handle_media_ref(items, item, idx)

        # remove disallowed items
        if removal:
            result[ITEMS] = [
                x for idx, x in enumerate(items) if idx not in removal
            ]

        if self.is_legacy_ipad:
            result[COLLECTION_ITEMS] = result[ITEMS]
            del result[ITEMS]


@component.adapter(INTICourseOverviewGroup)
class _NTICourseOverviewGroupDecorator(_VisibleMixinDecorator):

    @Lazy
    def is_legacy_ipad(self):
        result = is_legacy_uas(self.request, LEGACY_UAS_40)
        return result

    def _is_legacy_discussion(self, item):
        nttype = get_type(item.target)
        return nttype in (NTIID_TYPE_COURSE_TOPIC, NTIID_TYPE_COURSE_SECTION_TOPIC)

    def _is_viewable_discussion(self, item):
        target_discussion = find_object_with_ntiid(item.target)
        return target_discussion is not None \
            and has_permission(ACT_READ, target_discussion, self.request)

    @Lazy
    def _is_editor(self):
        return has_permission(ACT_CONTENT_EDIT, self.request.context)

    def _filter_legacy_discussions(self, context, indexes, removal, record):
        items = context.Items
        scope = record.Scope if record is not None else None
        scope = ES_CREDIT if scope == ES_ALL else scope  # map to credit
        m_scope = ENROLLMENT_LINEAGE_MAP.get(scope or u'')
        if not m_scope:
            removal.update(indexes)
        else:
            scopes = {}
            has_credit = False
            for idx in indexes:
                item = items[idx]
                specific = get_specific(item.target)
                scopes[idx] = ES_PUBLIC if OPEN in specific else None
                scopes[idx] = ES_CREDIT if IN_CLASS_SAFE in specific else scopes[idx]
                has_credit = has_credit or scopes[idx] == ES_CREDIT

            m_scope = m_scope[0]  # pick first
            for idx in indexes:
                item = items[idx]
                scope = scopes[idx]
                if not scope:
                    removal.add(idx)
                elif m_scope == ES_PUBLIC and scope != ES_PUBLIC:
                    removal.add(idx)
                elif m_scope == ES_CREDIT and scope == ES_PUBLIC and has_credit:
                    removal.add(idx)

    def _allow_discussion_course_bundle(self, context, item, record):
        resolved = resolve_discussion_course_bundle(user=self.remoteUser,
                                                    item=item,
                                                    context=context,
                                                    record=record)
        return bool(resolved is not None)

    def _allow_assessmentref(self, iface, item, record, course, target_ntiids=None, show_unpublished=False):
        assg = iface(item, None)
        # We want to return all assignment refs if in edit mode; otherwise
        # we want to exclude refs pointing to objects not in our target_ntiids.
        if     assg is None \
            or (    not show_unpublished
                and target_ntiids
                and assg.ntiid not in target_ntiids):
            return False
        if self._is_editor:
            return True
        # Instructor
        if record.Scope == ES_ALL:
            return True
        predicate = get_course_assessment_predicate_for_user(self.remoteUser,
                                                             course)
        result = predicate is not None and predicate(assg)
        return result

    def allow_assignmentref(self, item, record, course, target_ntiids, show_unpublished):
        result = self._allow_assessmentref(IQAssignment, item, record, course, target_ntiids, show_unpublished)
        return result

    def allow_surveyref(self, item, record, course):
        result = self._allow_assessmentref(IQSurvey, item, record, course)
        return result

    def allow_mediaroll(self, ext_item):
        key = COLLECTION_ITEMS if self.is_legacy_ipad else ITEMS
        value = ext_item.get(key)
        return bool(value)

    def _handle_slidedeck_ref(self, items, item, idx):
        source = INTISlideDeck(item, None)
        if source is not None:
            items[idx] = to_external_object(source)
            return True
        return False

    def _handle_timeline_ref(self, items, item, idx):
        source = INTITimeline(item, None)
        if source is not None:
            # See note in `_handle_media_ref`
            items[idx] = ext_obj = to_external_object(source,
                                                      useCache=False)
            if source != item:
                add_ref_rel(ext_obj, item)
            return True
        return False

    def _handle_calendar_event_ref(self, items, item, idx, course):
        # if event is not in the course, it doesn't show.
        source = ICalendarEvent(item, None)
        if source is not None and source.__parent__ is not None:
            calendar = ICalendar(course)
            return bool(source.__parent__ == calendar)
        return False

    def _can_view_ref_target(self, ref, course):
        target = find_object_with_ntiid(ref.target)
        result = can_view_publishable(target, self.request)
        if result and is_internal_file_link(ref.href):
            content_file = get_file_from_external_link(ref.href)
            if ICourseContentFile.providedBy(content_file):
                # We could check read permission here, but that may return
                # content from other courses, which would be confusing for
                # editors. So we can simply check the course lines up.
                file_course = find_interface(content_file, ICourseInstance, strict=True)
                # If file is stored in parent course, all child courses should
                # be able to see it.
                result = not ICourseSubInstance.providedBy(file_course) \
                      or course == file_course
        return result

    def _handle_relatedworkref_pointer(self, context, items, course, item, idx):
        source = INTIRelatedWorkRef(item, None)
        if      source is not None \
            and self._allow_visible(context, source) \
            and self._can_view_ref_target(source, course):
            items[idx] = to_external_object(source)
            return True
        return False

    def _handle_media_ref(self, items, item, idx, courses):
        source = INTIMedia(item, None)
        if source is not None:
            if is_video_included(source, courses=courses):
                # For duplicate videos in a lesson (rare?) we want to accurately
                # decorate ref info for navigation purposes at a performance cost.
                items[idx] = ext_obj = to_external_object(source,
                                                          useCache=False)
                if source != item:
                    add_ref_rel(ext_obj, item)
                return True
        return False

    def _get_courses(self, course):
        return [course, get_parent_course(course)] if ICourseSubInstance.providedBy(course) else [course]

    def _decorate_external_impl(self, context, result):
        idx = 0
        removal = set()
        discussions = []
        items = result[ITEMS]
        record = self.record(context)
        # We prefer the request course instance, which should be a section if
        # the end-user is in that context. This way we can filter/exclude
        # assessments that are not available.
        course = ICourseInstance(self.request, None)
        if course is None:
            course = record.CourseInstance
        if course is None:
            course = find_interface(context, ICourseInstance)
        # Get our assignment set; we do not to return assessment refs across sections
        course_assignments = get_course_assignments(course,
                                                    do_filtering=True,
                                                    parent_course=True)
        assignment_ntiids = [x.ntiid for x in course_assignments]
        show_unpublished = not get_omit_published(self.request)

        courses = self._get_courses(course)

        # loop through sources
        for idx, item in enumerate(context):
            if IVisible.providedBy(item) and not self._allow_visible(context, item):
                removal.add(idx)
            elif INTIDiscussionRef.providedBy(item):
                if item.isCourseBundle():
                    if      not self._is_editor \
                        and not self._allow_discussion_course_bundle(context, item, record):
                        removal.add(idx)
                elif self._is_legacy_discussion(item):
                    discussions.append(idx)
                elif not self._is_viewable_discussion(item):
                    removal.add(idx)
            elif IMediaRef.providedBy(item) \
                and not self._handle_media_ref(items, item, idx, courses):
                removal.add(idx)
            elif    INTISlideDeckRef.providedBy(item) \
                and not self._handle_slidedeck_ref(items, item, idx):
                removal.add(idx)
            elif    INTITimelineRef.providedBy(item) \
                and not self._handle_timeline_ref(items, item, idx):
                removal.add(idx)
            elif    INTIRelatedWorkRefPointer.providedBy(item) \
                and not self._handle_relatedworkref_pointer(context, items, course, item, idx):
                removal.add(idx)
            elif    INTIAssignmentRef.providedBy(item) \
                and not self.allow_assignmentref(item, record, course, assignment_ntiids, show_unpublished):
                removal.add(idx)
            elif    INTISurveyRef.providedBy(item) \
                and not self.allow_surveyref(item, record, course):
                removal.add(idx)
            elif INTIMediaRoll.providedBy(item) and not self.allow_mediaroll(items[idx]):
                removal.add(idx)
            elif INTICalendarEventRef.providedBy(item) and not self._handle_calendar_event_ref(items, item, idx, course):
                removal.add(idx)

        # filter legacy discussions
        if discussions and not self._is_editor:
            self._filter_legacy_discussions(context, discussions, removal, record)

        # remove disallowed items
        if removal:
            result[ITEMS] = [
                x for idx, x in enumerate(items) if idx not in removal
            ]


@component.adapter(INTILessonOverview)
class _NTILessonOverviewDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Remove empty groups for non-editors.
    """

    def _predicate(self, context, unused_result):
        result = has_permission(ACT_CONTENT_EDIT, context, self.request)
        return not result

    def _do_decorate_external(self, unused_context, result):
        removal = set()
        items = result.get(ITEMS) or ()  # groups
        for idx, group in enumerate(items):
            if not group.get(ITEMS):
                removal.add(idx)
        # remove empty items
        if removal:
            result[ITEMS] = [
                x for idx, x in enumerate(items) if idx not in removal
            ]


def _path_exists_in_package(path, package):
    bucket = package.root
    if bucket is not None:
        path_parts = path.split(os.sep)
        for path_part in path_parts or ():
            bucket = bucket.getChildNamed(path_part)
            if bucket is None:
                break
    return bucket is not None


def _get_content_package(context, path, ntiids=()):
    # Prefer to use package in our lineage if possible.
    result = find_interface(context, IContentPackage, strict=False)
    if result is not None:
        return result
    # XXX: We would like context from clients.
    # Get the first available content package from the given ntiids.
    # This could be improved if we indexed/registered ContentUnits.
    courses = set()
    for ntiid in ntiids or ():
        obj = find_object_with_ntiid(ntiid)
        if ICourseCatalogEntry.providedBy(obj) or ICourseInstance.providedBy(obj):
            courses.add(obj)
        elif IContentPackage.providedBy(obj):
            result = obj
            break
        elif IContentUnit.providedBy(obj):
            result = find_interface(obj, IContentPackage, strict=False)
            if result is not None:
                break

    if result is None:
        # XXX: This is expensive; have to find the correct package inside our
        # course for this ref.
        for course in courses:
            for package in get_course_packages(course) or ():
                if _path_exists_in_package(path, package):
                    result = package
                    break
    return result


def _get_item_content_package(item, path):
    catalog = get_library_catalog()
    entries = catalog.get_containers(item)
    result = _get_content_package(item, path, entries) if entries else None
    return result


@component.adapter(INTISlide, IRequest)
@component.adapter(INTITimeline, IRequest)
@component.adapter(INTIRelatedWorkRef, IRequest)
@interface.implementer(IExternalMappingDecorator)
class _NTIAbsoluteURLDecorator(AbstractAuthenticatedRequestAwareDecorator):

    EXTERNAL_LINK_MIME_TYPE = 'application/vnd.nextthought.externallink'

    @Lazy
    def is_legacy_ipad(self):
        return is_legacy_uas(self.request, LEGACY_UAS_40)

    def _predicate(self, context, unused_result):
        return self._is_authenticated and self._should_process(context)

    def _should_process(self, obj):
        result = False
        if      INTITimeline.providedBy(obj) \
            and not is_internal_file_link(obj.href or ''):
            result = True
        elif    INTIRelatedWorkRef.providedBy(obj) \
            and obj.type in (self.EXTERNAL_LINK_MIME_TYPE, CONTENT_MIME_TYPE):
            result = True
        elif INTISlide.providedBy(obj):
            result = True
        return result

    def _do_decorate_external(self, context, result):
        package = None
        for name in ('href', 'icon', 'slideimage'):
            value = getattr(context, name, None)
            if value and not value.startswith('/') and '://' not in value:
                if     package is None \
                    or not _path_exists_in_package(value, package):
                    # We make sure each url is in the correct package.
                    package = _get_item_content_package(context, value)
                if package is not None:
                    mapper = IContentUnitHrefMapper(package.key.bucket, None)
                    location = mapper.href if mapper is not None else u''
                    value = urllib_parse.urljoin(location, value)
                    if self.is_legacy_ipad:  # for legacy ipad
                        value = urllib_parse.urljoin(self.request.host_url, value)
                    result[name] = value


@component.adapter(INTITranscript, IRequest)
@interface.implementer(IExternalMappingDecorator)
class _NTITranscriptURLDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, unused_context, unused_result):
        return self._is_authenticated

    def _package_bucket(self, context):
        package = find_interface(context, IContentPackage, strict=False)
        try:
            return package.key.bucket
        except AttributeError:
            return None

    def _do_decorate_external(self, context, result):
        bucket = self._package_bucket(context)
        mapper = IContentUnitHrefMapper(bucket, None)
        location = mapper.href if mapper is not None else ''
        for name in ('src', 'srcjsonp'):
            value = getattr(context, name, None)
            if IFile.providedBy(value):
                result[name] = to_external_file_link(value, True)
            elif location and value and not value.startswith('/') and '://' not in value:
                value = urllib_parse.urljoin(location, value)
                result[name] = value


@component.adapter(INTITimeline, IRequest)
@component.adapter(INTIRelatedWorkRef, IRequest)
@interface.implementer(IExternalMappingDecorator)
class _AssetContentFileDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, unused_context, unused_result):
        result = self._is_authenticated
        return result

    def _do_decorate_external(self, context, result):
        if is_internal_file_link(context.href):
            internal = get_file_from_external_link(context.href)
            ext_obj = to_external_object(internal)
            result['ContentFile'] = ext_obj


@component.adapter(INTIRelatedWorkRef, IRequest)
@interface.implementer(IExternalMappingDecorator)
class _RefTargetPublishDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        return self._is_authenticated and context.type == CONTENT_MIME_TYPE

    def _do_decorate_external(self, context, result):
        content = find_object_with_ntiid(context.target)
        if content is not None:
            target_publish_state = None
            if IPublishable.providedBy(content):
                target_publish_state = 'DefaultPublished' if content.is_published() else 'Unpublished'
            result['TargetPublishState'] = target_publish_state


@interface.implementer(IExternalMappingDecorator)
class _IPADLegacyReferenceDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, unused_context, unused_result):
        result = is_legacy_uas(self.request, LEGACY_UAS_40)
        return result

    def _do_decorate_external(self, context, result):
        if INTIAssignmentRef.providedBy(context):
            result[CLASS] = 'Assignment'
            result[MIMETYPE] = 'application/vnd.nextthought.assessment.assignment'
        elif INTIQuestionSetRef.providedBy(context):
            result[CLASS] = 'QuestionSet'
            result[MIMETYPE] = 'application/vnd.nextthought.naquestionset'
        elif INTIQuestionRef.providedBy(context):
            result[CLASS] = 'Question'
            result[MIMETYPE] = 'application/vnd.nextthought.naquestion'
        elif INTIDiscussionRef.providedBy(context):
            result[MIMETYPE] = 'application/vnd.nextthought.discussion'


@interface.implementer(IExternalMappingDecorator)
class _AssessmentRefEditLinkDecorator(AssessmentPolicyEditLinkDecorator):
    """
    Give editors and instructors policy edit links on assessment refs.
    """

    def _predicate(self, context, unused_result):
        assessment_context = find_object_with_ntiid(context.target)
        if assessment_context is not None:
            result = super(_AssessmentRefEditLinkDecorator, self)._predicate(context,
                                                                             unused_result)
        else:
            result = False
            logger.info('AssessmentRef target deleted? (%s) (%s)',
                        context.target,
                        context.ntiid)
        return result

    def get_context(self, context):
        return find_object_with_ntiid(context.target)


@interface.implementer(IExternalMappingDecorator)
class _AssignmentRefEditLinkDecorator(_AssessmentRefEditLinkDecorator):
    pass


@interface.implementer(IExternalMappingDecorator)
class _SurveyRefEditLinkDecorator(_AssessmentRefEditLinkDecorator):
    pass


@component.adapter(INTILessonOverview)
@interface.implementer(IExternalMappingDecorator)
class LessonRecursiveAuditLogLinkDecorator(BaseRecursiveAuditLogLinkDecorator):
    pass


@component.adapter(IPresentationAsset)
@interface.implementer(IExternalObjectDecorator)
class AssetCompletableItemDecorator(CompletableItemDecorator):
    """
    Decorate the :class:`ICompletableItem` with requirement information. This
    requires being able to adapt :class:`ICompletableItem` to the correct
    :class:`ICompletionContext`.

    The assets themselves may be :class:`ICompletableItems` and thus, already
    decorated; this should be overridden by :class:`ICompletableItem` objects
    pointed to by the asset, if applicable.
    """

    def _do_decorate_external(self, context, result):
        asset = IConcreteAsset(context, context)
        if      asset is not context \
            and ICompletableItem.providedBy(asset):
                # Decorate concrete asset data
                super(AssetCompletableItemDecorator, self)._do_decorate_external(asset, result)
        target = getattr(asset, 'target', '')
        if target and is_valid_ntiid_string(target):
            target = find_object_with_ntiid(target)
            if ICompletableItem.providedBy(target):
                # Decorate target data
                super(AssetCompletableItemDecorator, self)._do_decorate_external(target, result)
