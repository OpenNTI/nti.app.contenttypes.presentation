#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from datetime import datetime

import six
from nti.app.assessment.evaluations.utils import is_inquiry_closed

from zope import component
from zope import interface

from nti.app.assessment.common.utils import get_available_for_submission_beginning
from nti.app.assessment.common.utils import get_available_for_submission_ending

from nti.app.assessment.utils import get_course_from_request

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIAudioRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIQuestionRef
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTICalendarEventRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.externalization.singleton import Singleton

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable

from nti.traversal.traversal import find_interface

NTIID = StandardExternalFields.NTIID
CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

logger = __import__('logging').getLogger(__name__)


@component.adapter(INTICourseOverviewGroup)
@interface.implementer(IExternalObjectDecorator)
class _OverviewGroupDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        external['accentColor'] = original.color


@interface.implementer(IExternalObjectDecorator)
class _BaseAssetDecorator(Singleton):

    def decorateExternalObject(self, unused_original, external):
        if 'ntiid' in external:
            external[NTIID] = external.pop('ntiid')
        if 'target' in external:
            external['Target-NTIID'] = external.pop('target')


@component.adapter(INTIQuestionRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIQuestionRefDecorator(_BaseAssetDecorator):
    pass


@component.adapter(INTISlideDeckRef)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideDeckRefDecorator(_BaseAssetDecorator):
    pass


@component.adapter(INTITimelineRef)
@interface.implementer(IExternalObjectDecorator)
class _NTITimelineRefDecorator(_BaseAssetDecorator):
    pass


@interface.implementer(IExternalObjectDecorator)
class _BaseAssessmentRefDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_BaseAssessmentRefDecorator, self).decorateExternalObject(original, external)
        # Always pass through to our target.
        question_count = external.pop('question_count', None)
        target = find_object_with_ntiid(original.target)
        if target is not None:
            question_count = getattr(target, 'draw', None) \
                          or len(target.questions)
        external['question-count'] = str(question_count)
        external['TargetMimeType'] = getattr(target, 'mime_type', '')


@component.adapter(INTIQuestionSetRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIQuestionSetRefDecorator(_BaseAssessmentRefDecorator):
    pass


@component.adapter(INTISurveyRef)
@interface.implementer(IExternalObjectDecorator)
class _NTISurveyRefDecorator(_BaseAssessmentRefDecorator):

    def _get_course(self, ref):
        course = get_course_from_request()
        if course is None:
            course = find_interface(ref, ICourseInstance, strict=False)
        return course

    def decorateExternalObject(self, original, external):
        super(_NTISurveyRefDecorator, self).decorateExternalObject(original, external)
        target = find_object_with_ntiid(original.target)
        if target is not None:
            target_publish_state = None
            if IPublishable.providedBy(target):
                target_publish_state = 'DefaultPublished' if target.is_published() else 'Unpublished'
            external['TargetPublishState'] = target_publish_state
            external['TargetIsClosed'] = target.isClosed
            course = self._get_course(original)
            if course is not None:
                beginning = get_available_for_submission_beginning(target, course)
                external['TargetAvailableForSubmissionBeginning'] = beginning

                ending = get_available_for_submission_ending(target, course)
                external['TargetAvailableForSubmissionEnding'] = ending

                external['TargetIsClosed'] = is_inquiry_closed(target, beginning, ending)


@component.adapter(INTIAssignmentRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIAssignmentRefDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTIAssignmentRefDecorator, self).decorateExternalObject(original, external)
        target = find_object_with_ntiid(original.target)
        external['TargetMimeType'] = getattr(target, 'mime_type', '')
        if 'containerId' in external:
            external['ContainerId'] = external.pop('containerId')


@component.adapter(INTIDiscussionRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIDiscussionRefDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTIDiscussionRefDecorator, self).decorateExternalObject(original, external)
        # We used to map the Target-NTIID to the ref's NTIID here, but that interferes
        # with UI navigation.
        if 'target' in external:
            external['Target-NTIID'] = external.pop('target')


@component.adapter(INTIRelatedWorkRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIRelatedWorkRefDecorator(Singleton):

    def decorateExternalObject(self, unused_original, external):
        if 'byline' in external:
            external['creator'] = external['byline']  # legacy
        description = external.get('description')
        if description:
            # legacy
            external['desc'] = external['description'] = description.strip()
        if 'target' in external:
            # legacy
            external['target-ntiid'] = external['target']
            external['target-NTIID'] = external['target']
        if 'type' in external:
            external['targetMimeType'] = external['type']


@component.adapter(INTITimeline)
@interface.implementer(IExternalObjectDecorator)
class _NTITimelineDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTITimelineDecorator, self).decorateExternalObject(original, external)
        if 'description' in external:
            external['desc'] = external['description']
        inline = external.pop('suggested_inline', None)
        if inline is not None:
            external['suggested-inline'] = inline


@interface.implementer(IExternalObjectDecorator)
class _NTIBaseSlideDecoratorMixin(Singleton):

    def decorateExternalObject(self, original, external):
        if 'byline' in external:
            external['creator'] = external['byline']
        if CLASS in external:
            external['class'] = (external.get(CLASS) or '').lower()  # legacy
        if 'description' in external and not external['description']:
            external.pop('description')
        external['ntiid'] = external[NTIID] = original.ntiid


@component.adapter(INTISlide)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideDecorator(_NTIBaseSlideDecoratorMixin):

    def decorateExternalObject(self, original, external):
        super(_NTISlideDecorator, self).decorateExternalObject(original, external)
        for name in ("slidevideostart", "slidevideoend", "slidenumber"):
            value = external.get(name)
            if value is not None and not isinstance(value, six.string_types):
                external[name] = str(value)


@component.adapter(INTISlideVideo)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideVideoDecorator(_NTIBaseSlideDecoratorMixin):

    def decorateExternalObject(self, original, external):
        super(_NTISlideVideoDecorator, self).decorateExternalObject(original, external)
        if 'video_ntiid' in external:
            external['video-ntiid'] = external['video_ntiid']  # legacy


@component.adapter(INTISlideDeck)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideDeckDecorator(_NTIBaseSlideDecoratorMixin):

    def decorateExternalObject(self, original, external):
        super(_NTISlideDeckDecorator, self).decorateExternalObject(original, external)
        external['creator'] = original.byline


@component.adapter(INTIAudioRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIAudioRefDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTIAudioRefDecorator, self).decorateExternalObject(original, external)
        if MIMETYPE in external:
            external[MIMETYPE] = "application/vnd.nextthought.ntiaudio"


@component.adapter(INTIVideoRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIVideoRefDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTIVideoRefDecorator, self).decorateExternalObject(original, external)
        if MIMETYPE in external:
            external[MIMETYPE] = "application/vnd.nextthought.ntivideo"


@interface.implementer(IExternalObjectDecorator)
class _BaseMediaDecorator(Singleton):

    def decorateExternalObject(self, unused_original, external):
        if MIMETYPE in external:
            # legacy
            external['mimeType'] = external[MIMETYPE]

        if 'byline' in external:
            external['creator'] = external['byline']  # legacy

        if 'ntiid' in external and NTIID not in external:
            external[NTIID] = external['ntiid']  # alias

        for name in ('DCDescription', 'DCTitle'):
            external.pop(name, None)

        for source in external.get('sources') or ():
            source.pop(CREATED_TIME, None)
            source.pop(LAST_MODIFIED, None)


@component.adapter(INTIVideo)
@interface.implementer(IExternalObjectDecorator)
class _NTIVideoDecorator(_BaseMediaDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTIVideoDecorator, self).decorateExternalObject(original, external)
        if 'closed_caption' in external:
            external['closedCaptions'] = external['closed_caption']  # legacy
        # remove empty
        for name in ('poster', 'label', 'subtitle'):
            if name in external and not external[name]:
                del external[name]
        # copy label
        title = external.get('title')
        if title and not external.get('label'):
            external['label'] = title


@component.adapter(INTIAudio)
@interface.implementer(IExternalObjectDecorator)
class _NTIAudioDecorator(_BaseMediaDecorator):
    pass


@component.adapter(INTICalendarEventRef)
@interface.implementer(IExternalObjectDecorator)
class _NTICalendarEventRefDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTICalendarEventRefDecorator, self).decorateExternalObject(original, external)
        target = find_object_with_ntiid(original.target)
        external['TargetMimeType'] = getattr(target, 'mime_type', '')
