#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from zope import component
from zope import interface

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
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.externalization.singleton import SingletonMetaclass

from nti.ntiids.ntiids import find_object_with_ntiid

NTIID = StandardExternalFields.NTIID
CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTICourseOverviewGroup)
@interface.implementer(IExternalObjectDecorator)
class _OverviewGroupDecorator(object):

    def __init__(self, *args):
        pass

    def decorateExternalObject(self, original, external):
        external['accentColor'] = original.color


@interface.implementer(IExternalObjectDecorator)
class _BaseAssetDecorator(object):

    def __init__(self, *args):
        pass

    def decorateExternalObject(self, unused_original, external):
        if 'ntiid' in external:
            external[NTIID] = external.pop('ntiid')
        if 'target' in external:
            external['Target-NTIID'] = external.pop('target')


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTIQuestionRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIQuestionRefDecorator(_BaseAssetDecorator):
    pass


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTISlideDeckRef)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideDeckRefDecorator(_BaseAssetDecorator):
    pass


@six.add_metaclass(SingletonMetaclass)
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


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTIQuestionSetRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIQuestionSetRefDecorator(_BaseAssessmentRefDecorator):
    pass


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTISurveyRef)
@interface.implementer(IExternalObjectDecorator)
class _NTISurveyRefDecorator(_BaseAssessmentRefDecorator):
    pass


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTIAssignmentRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIAssignmentRefDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTIAssignmentRefDecorator, self).decorateExternalObject(original, external)
        if 'containerId' in external:
            external['ContainerId'] = external.pop('containerId')


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTIDiscussionRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIDiscussionRefDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTIDiscussionRefDecorator, self).decorateExternalObject(original, external)
        if 'target' in external:
            external['Target-NTIID'] = external.pop('target')
        if 'Target-NTIID' in external and not original.isCourseBundle():
            external[NTIID] = external['Target-NTIID']


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTIRelatedWorkRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIRelatedWorkRefDecorator(object):

    def __init__(self, *args):
        pass

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


@six.add_metaclass(SingletonMetaclass)
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
class _NTIBaseSlideDecoratorMixin(object):

    def decorateExternalObject(self, original, external):
        if 'byline' in external:
            external['creator'] = external['byline']
        if CLASS in external:
            external['class'] = (external.get(CLASS) or '').lower()  # legacy
        if 'description' in external and not external['description']:
            external.pop('description')
        external['ntiid'] = external[NTIID] = original.ntiid


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTISlide)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideDecorator(_NTIBaseSlideDecoratorMixin):

    def decorateExternalObject(self, original, external):
        super(_NTISlideDecorator, self).decorateExternalObject(original, external)
        for name in ("slidevideostart", "slidevideoend", "slidenumber"):
            value = external.get(name)
            if value is not None and not isinstance(value, six.string_types):
                external[name] = str(value)


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTISlideVideo)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideVideoDecorator(_NTIBaseSlideDecoratorMixin):

    def decorateExternalObject(self, original, external):
        super(_NTISlideVideoDecorator, self).decorateExternalObject(original, external)
        if 'video_ntiid' in external:
            external['video-ntiid'] = external['video_ntiid']  # legacy


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTISlideDeck)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideDeckDecorator(_NTIBaseSlideDecoratorMixin):

    def decorateExternalObject(self, original, external):
        super(_NTISlideDeckDecorator, self).decorateExternalObject(original, external)
        external['creator'] = original.byline


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTIAudioRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIAudioRefDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTIAudioRefDecorator, self).decorateExternalObject(original, external)
        if MIMETYPE in external:
            external[MIMETYPE] = "application/vnd.nextthought.ntiaudio"


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTIVideoRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIVideoRefDecorator(_BaseAssetDecorator):

    def decorateExternalObject(self, original, external):
        super(_NTIVideoRefDecorator, self).decorateExternalObject(original, external)
        if MIMETYPE in external:
            external[MIMETYPE] = "application/vnd.nextthought.ntivideo"


@interface.implementer(IExternalObjectDecorator)
class _BaseMediaDecorator(object):

    def __init__(self, *args):
        pass

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


@six.add_metaclass(SingletonMetaclass)
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


@six.add_metaclass(SingletonMetaclass)
@component.adapter(INTIAudio)
@interface.implementer(IExternalObjectDecorator)
class _NTIAudioDecorator(_BaseMediaDecorator):
    pass
