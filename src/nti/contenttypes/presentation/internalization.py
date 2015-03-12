#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
from collections import Mapping

from zope import interface
from zope import component

from persistent.list import PersistentList

from nti.common.string import map_string_adjuster

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.interfaces import IInternalObjectUpdater
from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from .interfaces import INTIAudio
from .interfaces import INTIVideo
from .interfaces import INTISlide
from .interfaces import INTITimeline
from .interfaces import INTISlideDeck
from .interfaces import INTIDiscussion
from .interfaces import INTISlideVideo
from .interfaces import INTIRelatedWork
from .interfaces import INTIAssignmentRef
from .interfaces import INTICourseOverviewGroup

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
CREATOR = StandardExternalFields.CREATOR
MIMETYPE = StandardExternalFields.MIMETYPE

@interface.implementer(IInternalObjectUpdater)
class _NTIMediaUpdater(InterfaceObjectIO):

	def fixCreator(self, parsed):
		if 'creator' in parsed:
			parsed[CREATOR] = parsed.pop('creator')
		return self
	
	def parseTranscripts(self, parsed):
		transcripts = parsed.get('transcripts')
		for idx, transcript in enumerate(transcripts or ()):
			if MIMETYPE not in transcript:
				transcript[MIMETYPE] = u'application/vnd.nextthought.ntitranscript'
			obj = find_factory_for(transcript)()
			transcripts[idx] = update_from_external_object(obj, transcript)
		return self
		
	def fixAll(self, parsed):
		self.fixCreator(parsed).parseTranscripts(parsed)
		return parsed
	
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.fixAll(map_string_adjuster(parsed))
		result = super(_NTIMediaUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result

@component.adapter(INTIVideo)
class _NTIVideoUpdater(_NTIMediaUpdater):

	_ext_iface_upper_bound = INTIVideo

	def parseSources(self, parsed):
		sources = parsed.get('sources')
		for idx, source in enumerate(sources or ()):
			if MIMETYPE not in source:
				source[MIMETYPE] = u'application/vnd.nextthought.ntivideosource'
			obj = find_factory_for(source)()
			sources[idx] = update_from_external_object(obj, source)
		return self

	def fixCloseCaption(self, parsed):
		if 'closedCaptions' in parsed:
			parsed['closed_caption'] = parsed['closedCaptions']
		elif 'closedCaption' in parsed:
			parsed['closed_caption'] = parsed['closedCaption']
		return self
	
	def fixAll(self, parsed):
		self.parseSources(parsed).parseTranscripts(parsed).fixCloseCaption(parsed).fixCreator(parsed)
		return parsed

@component.adapter(INTIAudio)
class _NTIAudioUpdater(_NTIMediaUpdater):

	_ext_iface_upper_bound = INTIAudio

	def parseSources(self, parsed):
		sources = parsed.get('sources')
		for idx, source in enumerate(sources or ()):
			if MIMETYPE not in source:
				source[MIMETYPE] = u'application/vnd.nextthought.ntiaudiosource'
			obj = find_factory_for(source)()
			sources[idx] = update_from_external_object(obj, source)
		return self

	def fixAll(self, parsed):
		self.fixCreator(parsed).parseSources(parsed).parseTranscripts(parsed)
		return parsed

@component.adapter(INTISlide)
@interface.implementer(IInternalObjectUpdater)
class _NTISlideUpdater(InterfaceObjectIO):
	
	_ext_iface_upper_bound = INTISlide
	
	def fixAll(self, parsed):
		for name, func in ( ("slidevideostart", float),
							("slidevideoend", float),
							("slidenumber", int)):
			
			value = parsed.get(name, None)
			if value is not None and isinstance(value, six.string_types):
				try:
					parsed[name] = func(value) 
				except (TypeError, ValueError):
					pass
		return self
		
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.fixAll(map_string_adjuster(parsed))
		result = super(_NTISlideUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result

@component.adapter(INTISlideVideo)
@interface.implementer(IInternalObjectUpdater)
class _NTISlideVideoUpdater(InterfaceObjectIO):
	
	_ext_iface_upper_bound = INTISlideVideo
	
	def fixAll(self, parsed):
		if 'creator' in parsed:
			parsed[CREATOR] = parsed.pop('creator')
		
		if 'video-ntiid' in parsed:
			parsed['video_ntiid'] = parsed.pop('video-ntiid')

		return self
		
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.fixAll(map_string_adjuster(parsed))
		result = super(_NTISlideVideoUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result

@component.adapter(INTISlideDeck)
@interface.implementer(IInternalObjectUpdater)
class _NTISlideDeckUpdater(InterfaceObjectIO):
	
	_ext_iface_upper_bound = INTISlideDeck
	
	def fixAll(self, parsed):
		if 'creator' in parsed:
			parsed[CREATOR] = parsed.pop('creator')

		if 'slidedeckid' in parsed and not parsed.get('ntiid'):
			parsed['ntiid'] = parsed['slidedeckid']

		if 'ntiid' in parsed and not parsed.get('slidedeckid'):
			parsed['slidedeckid'] = parsed['ntiid']

		return self
		
	def parseSlides(self, parsed):
		slides = PersistentList(parsed.get('Slides') or ())
		if slides:
			parsed['Slides'] = slides
		return self

	def parseVideos(self, parsed):
		videos = PersistentList(parsed.get('Videos') or ())
		if videos:
			parsed['Videos'] = videos
		return self
	
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		map_string_adjuster(parsed, recur=False)
		self.fixAll(parsed).parseSlides(parsed).parseVideos(parsed)
		result = super(_NTISlideDeckUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result

@component.adapter(INTITimeline)
@interface.implementer(IInternalObjectUpdater)
class _NTITimelineUpdater(InterfaceObjectIO):
	
	_ext_iface_upper_bound = INTITimeline
	
	def fixAll(self, parsed):
		if 'desc' in parsed:
			parsed['description'] = parsed.pop('desc')
		return self
	
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.fixAll(map_string_adjuster(parsed))
		result = super(_NTITimelineUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result

@component.adapter(INTIRelatedWork)
@interface.implementer(IInternalObjectUpdater)
class _NTIRelatedWorkUpdater(InterfaceObjectIO):
	
	_ext_iface_upper_bound = INTIRelatedWork
	
	def fixAll(self, parsed):
		if 'creator' in parsed:
			parsed[CREATOR] = parsed.pop('creator')
			
		if NTIID in parsed:
			parsed['ntiid'] = parsed.pop(NTIID)

		if 'desc' in parsed:
			parsed['description'] = parsed.pop('desc')
			
		for name in ('target-NTIID', 'target-ntiid', 'Target-NTIID'):
			if name in parsed:
				parsed['target'] = parsed.pop(name)
				break
		
		if 'targetMimeType' in parsed:
			parsed['type'] = parsed.pop('targetMimeType')
			
		return self
	
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.fixAll(map_string_adjuster(parsed))
		result = super(_NTIRelatedWorkUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result
_NTIRelatedWorkRefUpdater = _NTIRelatedWorkUpdater

@component.adapter(INTIDiscussion)
@interface.implementer(IInternalObjectUpdater)
class _NTIDiscussionUpdater(InterfaceObjectIO):
	
	_ext_iface_upper_bound = INTIDiscussion
	
	def fixAll(self, parsed):
		if NTIID in parsed:
			parsed['ntiid'] = parsed[NTIID]
		return self
	
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.fixAll(map_string_adjuster(parsed))
		result = super(_NTIDiscussionUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result

@component.adapter(INTIAssignmentRef)
@interface.implementer(IInternalObjectUpdater)
class _NTIAssignmentRefUpdater(InterfaceObjectIO):
	
	_ext_iface_upper_bound = INTIAssignmentRef
	
	def fixAll(self, parsed):
		if NTIID in parsed:
			parsed['ntiid'] = parsed[NTIID]
		
		if 'ContainerId' in parsed:
			parsed['containerId'] = parsed['ContainerId']

		for name in ('Target-NTIID', 'target-NTIID', 'target-ntiid'):
			if name in parsed:
				parsed['target'] = parsed.pop(name)
				break

		if not parsed.get('target') and parsed.get('ntiid'):
			parsed['target'] = parsed['ntiid']
		elif not parsed.get('ntiid') and parsed.get('target'):
			parsed['ntiid'] = parsed['target']
			
		if not parsed.get('title') and parsed.get('label'):
			parsed['title'] = parsed['label']
		elif not parsed.get('label') and parsed.get('title'):
			parsed['label'] = parsed['title']
			
		return self
	
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.fixAll(map_string_adjuster(parsed))
		result = super(_NTIAssignmentRefUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result

@component.adapter(INTICourseOverviewGroup)
@interface.implementer(IInternalObjectUpdater)
class _NTICourseOverviewGroupUpdater(InterfaceObjectIO):

	_ext_iface_upper_bound = INTICourseOverviewGroup
	
	def fixMimeTypes(self, parsed):
		items = PersistentList(parsed.get(ITEMS) or ())
		for idx, item in enumerate(items):
			if not isinstance(item, Mapping):
				continue

			# change legacy assignment references 
			mt = item.get(MIMETYPE)
			if mt == "application/vnd.nextthought.assessment.assignment":
				item[MIMETYPE] = u"application/vnd.nextthought.assignmentref"
				obj = find_factory_for(item)()
				items[idx] = update_from_external_object(obj, item)

		parsed[ITEMS] = items	
		return self
	
	def fixAll(self, parsed):
		self.fixMimeTypes(parsed)
		return parsed
	
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.fixAll(map_string_adjuster(parsed, recur=False))
		result = super(_NTICourseOverviewGroupUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result
