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
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.traversal.traversal import find_interface

from .utils import get_courses

from . import get_catalog

@interface.implementer(IACLProvider)
class BaseACLProvider(object):

	def __init__(self, context):
		self.context = context

	@property
	def __acl__(self):
		catalog = get_catalog()
		entries = catalog.get_containers(self.context)
		if entries:
			aces = []
			for course in get_courses(entries):
				acl = IACLProvider(course).__acl__
				aces.extend(acl or ())
			result = acl_from_aces( aces )
			return result
		return None

@interface.implementer(IACLProvider)
class BasePresentationAssetACLProvider(BaseACLProvider):

	@Lazy
	def __acl__(self):
		result = super(BasePresentationAssetACLProvider, self).__acl__
		if not result:
			ace = ace_allowing( IPrincipal(AUTHENTICATED_GROUP_NAME),
						 		(ACT_READ),
						   		BasePresentationAssetACLProvider )
			result = acl_from_aces( ace ) 
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

@component.adapter(INTILessonOverview)
@interface.implementer(IACLProvider)
class NTILessonOverviewACLProvider(BaseACLProvider):

	@Lazy
	def __acl__(self):
		result = super(NTILessonOverviewACLProvider, self).__acl__
		if not result:
			course = find_interface(self.context, ICourseInstance, strict=False)
			if course is not None:
				result = IACLProvider(course).__acl__
			else:
				result = [ACE_DENY_ALL]
		return result
