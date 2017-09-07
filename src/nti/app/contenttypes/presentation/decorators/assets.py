#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from urlparse import urljoin

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import ILocation

from pyramid.interfaces import IRequest

from nti.app.assessment.decorators.assignment import AssessmentPolicyEditLinkDecorator

from nti.app.contenttypes.presentation.decorators import LEGACY_UAS_40
from nti.app.contenttypes.presentation.decorators import VIEW_ORDERED_CONTENTS

from nti.app.contenttypes.presentation.decorators import is_legacy_uas
from nti.app.contenttypes.presentation.decorators import can_view_publishable
from nti.app.contenttypes.presentation.decorators import _AbstractMoveLinkDecorator

from nti.app.contenttypes.presentation.utils import is_item_visible

from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_TOPIC
from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC

from nti.app.products.courseware.decorators import BaseRecursiveAuditLogLinkDecorator

from nti.app.products.courseware.resources.utils import is_internal_file_link
from nti.app.products.courseware.resources.utils import to_external_file_link
from nti.app.products.courseware.resources.utils import get_file_from_external_link

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment

from nti.base.interfaces import IFile

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.discussions.utils import resolve_discussion_course_bundle

from nti.contenttypes.courses.interfaces import OPEN
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

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import IMediaRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
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
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer

from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import ACT_READ

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

from nti.ntiids.ntiids import get_type
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_provider_safe
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

LINKS = StandardExternalFields.LINKS
ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE
IN_CLASS_SAFE = make_provider_safe(IN_CLASS)

#: Legacy ipad key for item video rolls
COLLECTION_ITEMS = 'collectionItems'


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
            items[idx] = to_external_object(source)
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

    def _filter_legacy_discussions(self, context, indexes, removal):
        items = context.Items
        record = self.record(context)
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

    def _allow_discussion_course_bundle(self, context, item):
        record = self.record(context)
        resolved = resolve_discussion_course_bundle(user=self.remoteUser,
                                                    item=item,
                                                    context=context,
                                                    record=record)
        return bool(resolved is not None)

    def _allow_assessmentref(self, iface, context, item):
        if self._is_editor:
            return True
        assg = iface(item, None)
        if assg is None:
            return False
        # Instructor
        record = self.record(context)
        if record.Scope == ES_ALL:
            return True
        course = record.CourseInstance
        predicate = get_course_assessment_predicate_for_user(self.remoteUser,
                                                             course)
        result = predicate is not None and predicate(assg)
        return result

    def allow_assignmentref(self, context, item):
        result = self._allow_assessmentref(IQAssignment, context, item)
        return result

    def allow_surveyref(self, context, item):
        result = self._allow_assessmentref(IQSurvey, context, item)
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
            items[idx] = to_external_object(source)
            return True
        return False

    def _can_view_ref_target(self, ref):
        target = find_object_with_ntiid(ref.target)
        return can_view_publishable(target, self.request)

    def _handle_relatedworkref_pointer(self, context, items, item, idx):
        source = INTIRelatedWorkRef(item, None)
        if      source is not None \
            and self._allow_visible(context, source) \
            and self._can_view_ref_target(source):
            items[idx] = to_external_object(source)
            return True
        return False

    def _decorate_external_impl(self, context, result):
        idx = 0
        removal = set()
        discussions = []
        items = result[ITEMS]

        # loop through sources
        for idx, item in enumerate(context):
            if IVisible.providedBy(item) and not self._allow_visible(context, item):
                removal.add(idx)
            elif INTIDiscussionRef.providedBy(item):
                if item.isCourseBundle():
                    if      not self._is_editor \
                        and not self._allow_discussion_course_bundle(context, item):
                        removal.add(idx)
                elif self._is_legacy_discussion(item):
                    discussions.append(idx)
                elif not self._is_viewable_discussion(item):
                    removal.add(idx)
            elif IMediaRef.providedBy(item):
                self._handle_media_ref(items, item, idx)
            elif    INTISlideDeckRef.providedBy(item) \
                and not self._handle_slidedeck_ref(items, item, idx):
                removal.add(idx)
            elif    INTITimelineRef.providedBy(item) \
                and not self._handle_timeline_ref(items, item, idx):
                removal.add(idx)
            elif    INTIRelatedWorkRefPointer.providedBy(item) \
                and not self._handle_relatedworkref_pointer(context, items, item, idx):
                removal.add(idx)
            elif    INTIAssignmentRef.providedBy(item) \
                and not self.allow_assignmentref(context, item):
                removal.add(idx)
            elif    INTISurveyRef.providedBy(item) \
                and not self.allow_surveyref(context, item):
                removal.add(idx)
            elif INTIMediaRoll.providedBy(item) and not self.allow_mediaroll(items[idx]):
                removal.add(idx)

        # filter legacy discussions
        if discussions and not self._is_editor:
            self._filter_legacy_discussions(context, discussions, removal)

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


@component.adapter(INTITimeline, IRequest)
@component.adapter(INTIRelatedWorkRef, IRequest)
@interface.implementer(IExternalMappingDecorator)
class _NTIAbsoluteURLDecorator(AbstractAuthenticatedRequestAwareDecorator):

    CONTENT_MIME_TYPE = 'application/vnd.nextthought.content'
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
            and obj.type in (self.EXTERNAL_LINK_MIME_TYPE, self.CONTENT_MIME_TYPE):
            result = True
        return result

    def _do_decorate_external(self, context, result):
        package = None
        for name in ('href', 'icon'):
            value = getattr(context, name, None)
            if value and not value.startswith('/') and '://' not in value:
                if     package is None \
                    or not _path_exists_in_package(value, package):
                    # We make sure each url is in the correct package.
                    package = _get_item_content_package(context, value)
                if package is not None:
                    mapper = IContentUnitHrefMapper(package.key.bucket, None)
                    location = mapper.href if mapper is not None else u''
                    value = urljoin(location, value)
                    if self.is_legacy_ipad:  # for legacy ipad
                        value = urljoin(self.request.host_url, value)
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
                value = urljoin(location, value)
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
