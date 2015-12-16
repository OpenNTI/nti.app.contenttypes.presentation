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

from nti.contenttypes.courses.discussions.utils import get_discussion_for_path

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTIAudioRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIAudioRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTIVideoRoll
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.ntiids.ntiids import get_parts
from nti.ntiids.interfaces import INTIIDResolver

from .utils import resolve_discussion_course_bundle
from .utils import get_course_by_relative_path_parts

@interface.implementer(INTIIDResolver)
class _PresentationResolver(object):

	_ext_iface = IPresentationAsset

	def resolve(self, key):
		result = component.queryUtility(self._ext_iface, name=key)
		return result

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

class _NTITimeLineResolver(_PresentationResolver):
	_ext_iface = INTITimeline

class _NTISlideDeckResolver(_PresentationResolver):
	_ext_iface = INTISlideDeck

class _NTIRelatedWorkRefResolver(_PresentationResolver):
	_ext_iface = INTIRelatedWorkRef

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

	@property
	def remoteUser(self):
		return get_remote_user()

	def get_course(self, splits=()):
		if splits and len(splits) >= 2:  # by parts e.g Fall2015:BIOL_2124
			result = get_course_by_relative_path_parts(*splits[:2])
			return result
		return None

	def get_discussion(self, splits, course=None):
		course = self.get_course(splits) if course is None else course
		path = os.path.sep.join(splits[2:]) if len(splits or ()) >= 3 else None
		if course is not None and path:
			result = get_discussion_for_path(path, course)
			return result
		return None

	def resolve(self, key):
		user = self.remoteUser
		if user is not None:
			parts = get_parts(key) if key else None
			specific = parts.specific if parts else None
			splits = specific.split(self.separator) if specific else ()
			course = self.get_course(splits)
			discussion = self.get_discussion(splits, course)
			if discussion is not None:
				result = resolve_discussion_course_bundle(user, discussion, course)
				return result
		return None
