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

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIRelatedWork
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.ntiids.interfaces import INTIIDResolver

@interface.implementer(INTIIDResolver)
class _PresentationResolver(object):

    _ext_iface = None
    
    def resolve( self, key ):
        result = component.queryUtility(self._ext_iface, name=key)
        return result

class _NTIAudioResolver(_PresentationResolver):
    _ext_iface = INTIAudio
    
class _NTIVideoResolver(_PresentationResolver):
    _ext_iface = INTIVideo
    
class _NTISlideResolver(_PresentationResolver):
    _ext_iface = INTISlide
    
class _NTISlideVideoResolver(_PresentationResolver):
    _ext_iface = INTISlideVideo

class _NTITimeLineResolver(_PresentationResolver):
    _ext_iface = INTITimeline

class _NTISlideDeckResolver(_PresentationResolver):
    _ext_iface = INTISlideDeck

class _NTIRelatedWorkResolver(_PresentationResolver):
    _ext_iface = INTIRelatedWork

class _NTIDiscussionRefResolver(_PresentationResolver):
    _ext_iface = INTIDiscussionRef
    
class _GroupOverViewableResolver(_PresentationResolver):
    _ext_iface = IGroupOverViewable

class _NTILessonOverviewResolver(_PresentationResolver):
    _ext_iface = INTILessonOverview

class _NTICourseOverviewGroupResolver(_PresentationResolver):
    _ext_iface = INTICourseOverviewGroup
