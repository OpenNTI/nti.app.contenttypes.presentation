#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.security.interfaces import IPrincipal

from nti.common.property import Lazy

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIAudioRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTIVideoRoll
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import IACLProvider

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import ROLE_CONTENT_EDITOR

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.traversal.traversal import find_interface

from .utils import get_presentation_asset_courses

@interface.implementer(IACLProvider)
class BasePresentationAssetACLProvider(object):

	def __init__(self, context):
		self.context = context

	@property
	def __acl__(self):
		instructors = set()
		aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
				ace_allowing(ROLE_CONTENT_EDITOR, ALL_PERMISSIONS, type(self))]
		courses = get_presentation_asset_courses(self.context)
		for course in courses or ():
			for scope in course.SharingScopes.values():
				aces.append(ace_allowing(IPrincipal(scope), ACT_READ, type(self)))

			for i in course.instructors or (): # get special powers
				instructors.add(ace_allowing(i, ALL_PERMISSIONS, type(self)))
				instructors.add(ace_allowing(i, ACT_CONTENT_EDIT, type(self)))

		aces.extend(instructors)
		result = acl_from_aces(aces)
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

@component.adapter(INTIAudioRoll)
class NTIAudioRollACLProvider(BasePresentationAssetACLProvider):
	pass

@component.adapter(INTIVideoRoll)
class NTIVideoRollACLProvider(BasePresentationAssetACLProvider):
	pass

@component.adapter(INTISlideDeck)
class NTISlideDeckACLProvider(BasePresentationAssetACLProvider):
	pass

@component.adapter(INTIRelatedWorkRef)
class NTIRelatedWorkRefACLProvider(BasePresentationAssetACLProvider):
	pass

@component.adapter(INTITimeline)
class NTITimelineACLProvider(BasePresentationAssetACLProvider):
	pass

@component.adapter(INTISlideVideo)
class NTISlideVideoACLProvider(BasePresentationAssetACLProvider):
	pass

@interface.implementer(IACLProvider)
@component.adapter(INTICourseOverviewGroup)
class NTICourseOverviewGroupACLProvider(object):

	def __init__(self, context):
		self.context = context

	@property
	def __parent__(self):
		return self.context.__parent__

	@Lazy
	def __acl__(self):
		aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
				ace_allowing(ROLE_CONTENT_EDITOR, ALL_PERMISSIONS, type(self))]
		course = find_interface(self.context, ICourseInstance, strict=False)
		if course is None:
			aces.append(ACE_DENY_ALL)
		result = acl_from_aces(aces)
		return result

@interface.implementer(IACLProvider)
@component.adapter(INTILessonOverview)
class NTILessonOverviewACLProvider(object):

	def __init__(self, context):
		self.context = context

	@property
	def __parent__(self):
		return self.context.__parent__

	@Lazy
	def __acl__(self):
		aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
				ace_allowing(ROLE_CONTENT_EDITOR, ALL_PERMISSIONS, type(self))]
		course = find_interface(self.context, ICourseInstance, strict=False)
		if course is None:
			aces.append(ACE_DENY_ALL)
		result = acl_from_aces(aces)
		return result
