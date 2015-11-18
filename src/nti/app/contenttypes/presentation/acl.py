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
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ACE_ACT_ALLOW
from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.dataserver.interfaces import IACLProvider

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_EDITOR

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.traversal.traversal import find_interface

from .utils import get_presentation_asset_courses

@interface.implementer(IACLProvider)
class BaseACLProvider(object):

	def __init__(self, context):
		self.context = context

	@property
	def __acl__(self):
		aces = []
		deny = set()
		allow = set()
		courses = get_presentation_asset_courses(self.context)
		for course in courses or ():
			acl = IACLProvider(course).__acl__  # courses have an ACL provider
			for ace in acl or ():
				s = allow if ace.action == ACE_ACT_ALLOW else deny
				s.add(ace)
		# Make sure allows come first for performance.
		aces.extend(allow)
		aces.extend(deny)
		result = acl_from_aces(aces) if aces else None
		return result

@interface.implementer(IACLProvider)
class BasePresentationAssetACLProvider(BaseACLProvider):

	@Lazy
	def __acl__(self):
		result = super(BasePresentationAssetACLProvider, self).__acl__
		if not result:
			ace = ace_allowing(IPrincipal(AUTHENTICATED_GROUP_NAME),
						 		(ACT_READ),
						   		type(self))
			result = acl_from_aces(ace)
		result.insert(0, ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)))
		return result

@component.adapter(IPresentationAsset)
class PresentationAssetACLProvider(BasePresentationAssetACLProvider):
	pass

@component.adapter(INTIAudio)
@interface.implementer(IACLProvider)
class NTIAudioACLProvider(BasePresentationAssetACLProvider):
	pass

@component.adapter(INTIVideo)
@interface.implementer(IACLProvider)
class NTIVideoACLProvider(BasePresentationAssetACLProvider):
	pass

@component.adapter(INTISlideDeck)
@interface.implementer(IACLProvider)
class NTISlideDeckACLProvider(BasePresentationAssetACLProvider):
	pass

@interface.implementer(IACLProvider)
@component.adapter(INTIRelatedWorkRef)
class NTIRelatedWorkRefACLProvider(BasePresentationAssetACLProvider):
	pass

@component.adapter(INTITimeline)
@interface.implementer(IACLProvider)
class NTITimelineACLProvider(BasePresentationAssetACLProvider):
	pass

@component.adapter(INTISlideVideo)
@interface.implementer(IACLProvider)
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
		result = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
				  ace_allowing(ROLE_CONTENT_EDITOR, ALL_PERMISSIONS, type(self))]
		course = find_interface(self.context, ICourseInstance, strict=False)
		if course is None:
			result.append(ACE_DENY_ALL)
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
		result = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
				  ace_allowing(ROLE_CONTENT_EDITOR, ALL_PERMISSIONS, type(self))]
		course = find_interface(self.context, ICourseInstance, strict=False)
		if course is None:
			result.append(ACE_DENY_ALL)
		return result
