#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.security.interfaces import IPrincipal

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_courses

from nti.app.contentfile.acl import ContentBaseFileACLProvider

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTITranscript
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTITranscriptFile
from nti.contenttypes.presentation.interfaces import IUserCreatedTranscript
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import ILegacyPresentationAsset
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraint
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraints

from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_SITE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import IACLProvider

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IACLProvider)
class BasePresentationAssetACLProvider(object):

    def __init__(self, context):
        self.context = context

    @property
    def __acl__(self):
        result = acl_from_aces(ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)))
        result.append(ace_allowing(ROLE_CONTENT_ADMIN,
                                   ALL_PERMISSIONS, type(self)))
        result.append(ace_allowing(ROLE_SITE_ADMIN,
                                   ALL_PERMISSIONS, type(self)))
        courses = get_presentation_asset_courses(self.context)
        for course in courses or ():
            result.extend(IACLProvider(course).__acl__)
        # If legacy, let parent objects determine ACL.
        if not ILegacyPresentationAsset.providedBy(self.context):
            result.append(ACE_DENY_ALL)
        return result


@component.adapter(IPresentationAsset)
class PresentationAssetACLProvider(BasePresentationAssetACLProvider):
    pass


@component.adapter(INTIAudio)
class NTIAudioACLProvider(BasePresentationAssetACLProvider):
    pass


@component.adapter(INTIVideo)
class NTIVideoACLProvider(BasePresentationAssetACLProvider):
    pass


@component.adapter(INTIRelatedWorkRef)
class NTIRelatedWorkRefACLProvider(BasePresentationAssetACLProvider):
    pass


@component.adapter(INTITimeline)
class NTITimelineACLProvider(BasePresentationAssetACLProvider):
    pass


@component.adapter(INTISlideDeck)
class NTISlideDeckACLProvider(BasePresentationAssetACLProvider):
    pass


@component.adapter(INTISlideVideo)
class NTISlideVideoACLProvider(BasePresentationAssetACLProvider):
    pass


class AbstractCourseLineageACLProvider(object):

    def __init__(self, context):
        self.context = context

    @property
    def __parent__(self):
        return self.context.__parent__

    @Lazy
    def __acl__(self):
        result = acl_from_aces(ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)))
        course = find_interface(self.context, ICourseInstance, strict=False)
        if course is not None:
            result.extend(IACLProvider(course).__acl__)
        result.append(ACE_DENY_ALL)
        return result


@component.adapter(INTITimelineRef)
@interface.implementer(IACLProvider)
class NTITimelineRefACLProvider(AbstractCourseLineageACLProvider):
    pass


@component.adapter(INTISlideDeckRef)
@interface.implementer(IACLProvider)
class NTISlideDeckRefACLProvider(AbstractCourseLineageACLProvider):
    pass


@component.adapter(INTIMediaRoll)
@interface.implementer(IACLProvider)
class NTIMediaRollACLProvider(AbstractCourseLineageACLProvider):
    pass


@interface.implementer(IACLProvider)
@component.adapter(INTICourseOverviewGroup)
class NTICourseOverviewGroupACLProvider(AbstractCourseLineageACLProvider):
    pass


@interface.implementer(IACLProvider)
@component.adapter(INTILessonOverview)
class NTILessonOverviewACLProvider(AbstractCourseLineageACLProvider):
    pass


@interface.implementer(IACLProvider)
class AdminEditorParentObjectACLProvider(object):

    def __init__(self, context):
        self.context = context

    @property
    def __parent__(self):
        return self.context.__parent__

    @Lazy
    def __acl__(self):
        result = acl_from_aces(ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)))
        result.append(ace_allowing(ROLE_CONTENT_ADMIN,
                                   ALL_PERMISSIONS, type(self)))
        result.append(ace_allowing(ROLE_SITE_ADMIN,
                                   ALL_PERMISSIONS, type(self)))
        return result


@component.adapter(INTITranscriptFile)
class NTITranscriptFileACLProvider(ContentBaseFileACLProvider):
    pass


@component.adapter(INTITranscript)
class NTITranscriptACLProvider(AdminEditorParentObjectACLProvider):

    @Lazy
    def __acl__(self):
        result = super(NTITranscriptACLProvider, self).__acl__
        if IUserCreatedTranscript.providedBy(self.context):
            creator = IPrincipal(self.context.creator, None)
            if creator is not None:
                result.append(ace_allowing(creator, ALL_PERMISSIONS, type(self)))
        return result


@component.adapter(ILessonPublicationConstraint)
class LessonPublicationConstraintACLProvider(AdminEditorParentObjectACLProvider):
    pass


@component.adapter(ILessonPublicationConstraints)
class LessonPublicationConstraintsACLProvider(AdminEditorParentObjectACLProvider):
    pass
