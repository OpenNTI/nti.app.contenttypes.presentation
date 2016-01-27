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

from nti.app.contenttypes.presentation.utils import get_presentation_asset_courses

from nti.common.property import Lazy

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import IACLProvider

from nti.traversal.traversal import find_interface

@interface.implementer(IACLProvider)
class BasePresentationAssetACLProvider(object):

	def __init__(self, context):
		self.context = context

	@property
	def __acl__(self):
		result = acl_from_aces(ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)))
		courses = get_presentation_asset_courses(self.context)
		for course in courses or ():
			result.extend(IACLProvider(course).__acl__)
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
