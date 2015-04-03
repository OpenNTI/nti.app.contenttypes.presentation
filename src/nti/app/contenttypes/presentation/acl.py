#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.security.interfaces import IPrincipal

from nti.common.property import Lazy

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.dataserver.interfaces import IACLProvider

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.traversal.traversal import find_interface

@component.adapter(IPresentationAsset)
@interface.implementer(IACLProvider)
class PresentationAssetACLProvider(object):

	def __init__(self, context):
		self.context = context

	@Lazy
	def __acl__(self):
		ace = ace_allowing( IPrincipal(AUTHENTICATED_GROUP_NAME),
					 		(ACT_READ),
					   		PresentationAssetACLProvider )
		result = acl_from_aces( ace ) 
		return result

@component.adapter(INTILessonOverview)
@interface.implementer(IACLProvider)
class NTILessonOverviewACLProvider(object):

	def __init__(self, context):
		self.context = context

	@Lazy
	def __acl__(self):
		course = find_interface(self.context, ICourseInstance, strict=False)
		if course is not None:
			result = IACLProvider(course).__acl__
		else:
			result = [ACE_DENY_ALL]
		return result