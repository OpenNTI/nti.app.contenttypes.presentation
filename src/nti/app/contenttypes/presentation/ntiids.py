#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from zope import component
from zope import interface

from nti.app.authentication import get_remote_user

from nti.app.contenttypes.presentation.utils import resolve_discussion_course_bundle
from nti.app.contenttypes.presentation.utils import get_course_by_relative_path_parts

from nti.contenttypes.courses.discussions.utils import get_discussion_for_path

from nti.contenttypes.presentation import NTI_AUDIO
from nti.contenttypes.presentation import NTI_VIDEO
from nti.contenttypes.presentation import NTI_LESSON_OVERVIEW

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTIAudioRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIAudioRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTIVideoRoll
from nti.contenttypes.presentation.interfaces import INTIInquiryRef
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIQuestionRef
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraints

from nti.ntiids.interfaces import INTIIDResolver

from nti.ntiids.ntiids import get_parts
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import find_object_with_ntiid


@interface.implementer(INTIIDResolver)
class _PresentationResolver(object):

    _ext_iface = IPresentationAsset

    def resolve(self, key):
        result = component.queryUtility(self._ext_iface, name=key)
        return result


class _NTIQuestionRef(_PresentationResolver):
    _ext_iface = INTIQuestionRef


class _NTIQuestionSetRef(_PresentationResolver):
    _ext_iface = INTIQuestionSetRef


class _NTIAssignmentRef(_PresentationResolver):
    _ext_iface = INTIAssignmentRef


class _NTIInquiryRef(_PresentationResolver):
    _ext_iface = INTIInquiryRef


class _NTIAudioRefResolver(_PresentationResolver):
    _ext_iface = INTIAudioRef


class _NTIAudioResolver(_PresentationResolver):
    _ext_iface = INTIAudio


class _NTIVideoRefResolver(_PresentationResolver):
    _ext_iface = INTIVideoRef


class _NTIVideoResolver(_PresentationResolver):
    _ext_iface = INTIVideo


class _NTIAudioRollResolver(_PresentationResolver):
    _ext_iface = INTIAudioRoll


class _NTIVideoRollResolver(_PresentationResolver):
    _ext_iface = INTIVideoRoll


class _NTISlideResolver(_PresentationResolver):
    _ext_iface = INTISlide


class _NTISlideVideoResolver(_PresentationResolver):
    _ext_iface = INTISlideVideo


class _NTITimelineResolver(_PresentationResolver):
    _ext_iface = INTITimeline


class _NTITimelineRefResolver(_PresentationResolver):
    _ext_iface = INTITimelineRef


class _NTISlideDeckResolver(_PresentationResolver):
    _ext_iface = INTISlideDeck


class _NTISlideDeckRefResolver(_PresentationResolver):
    _ext_iface = INTISlideDeckRef


class _NTIRelatedWorkRefResolver(_PresentationResolver):
    _ext_iface = INTIRelatedWorkRef


class _NTIRelatedWorkRefPointerResolver(_PresentationResolver):
    _ext_iface = INTIRelatedWorkRefPointer


class _NTIDiscussionRefResolver(_PresentationResolver):
    _ext_iface = INTIDiscussionRef


class _GroupOverViewableResolver(_PresentationResolver):
    _ext_iface = IGroupOverViewable


class _NTILessonOverviewResolver(_PresentationResolver):
    _ext_iface = INTILessonOverview


class _NTICourseOverviewGroupResolver(_PresentationResolver):
    _ext_iface = INTICourseOverviewGroup


@interface.implementer(INTIIDResolver)
class _NTICourseBundleResolver(object):

    separator = ':'

    def get_course(self, splits=()):
        if splits and len(splits) >= 2:  # by parts e.g Fall2015:BIOL_2124
            return get_course_by_relative_path_parts(splits[:2])
        return None

    def get_discussion(self, splits, course=None):
        course = self.get_course(splits) if course is None else course
        path = os.path.sep.join(splits[2:]) if len(splits or ()) >= 3 else None
        if course is not None and path:
            result = get_discussion_for_path(path, course)
            return result
        return None

    def resolve(self, key):
        user = get_remote_user()
        if user is not None:
            parts = get_parts(key) if key else None
            specific = parts.specific if parts else None
            splits = specific.split(self.separator) if specific else ()
            course = self.get_course(splits)
            discussion = self.get_discussion(splits, course)
            if discussion is not None:
                result = resolve_discussion_course_bundle(user,
                                                          discussion,
                                                          course)
                if result:
                    _, topic = result
                    return topic
        return None


@interface.implementer(INTIIDResolver)
class _NTITranscriptResolver(object):

    def resolve(self, key):
        parts = get_parts(key)
        specific = parts.specific[:parts.specific.rfind('.')]
        for nttype in (NTI_VIDEO, NTI_AUDIO):
            # transform to a media NTIID
            ntiid = make_ntiid(nttype=nttype,
                               date=parts.date,
                               specific=specific,
                               provider=parts.provider)
            media = find_object_with_ntiid(ntiid)
            if INTIMedia.providedBy(media):
                for transcript in media.transcripts or ():
                    if transcript.ntiid == key:
                        return transcript
        return None


@interface.implementer(INTIIDResolver)
class _NTILessonCompletionConstraintResolver(object):

    def resolve(self, key):
        parts = get_parts(key)
        specific = parts.specific[:parts.specific.rfind('.')]
        ntiid = make_ntiid(date=parts.date,
                           specific=specific,
                           provider=parts.provider,
                           nttype=NTI_LESSON_OVERVIEW)
        lesson = find_object_with_ntiid(ntiid)
        if INTILessonOverview.providedBy(lesson):
            constraints = ILessonPublicationConstraints(lesson)
            for constraint in constraints.Items:
                if constraint.ntiid == key:
                    return constraint
        return None
