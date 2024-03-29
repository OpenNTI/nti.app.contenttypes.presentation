#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import copy
from itertools import chain
from collections import Mapping
from six.moves import urllib_parse

import transaction

from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy

from zope.event import notify as event_notify

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import get_safe_source_filename
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile import validate_sources

from nti.app.contentfolder.resources import is_internal_file_link
from nti.app.contentfolder.resources import to_external_file_link
from nti.app.contentfolder.resources import get_file_from_external_link

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.interfaces import ICoursePresentationAssets

from nti.app.contenttypes.presentation.utils.asset import intid_register
from nti.app.contenttypes.presentation.utils.asset import add_2_connection
from nti.app.contenttypes.presentation.utils.asset import make_asset_ntiid
from nti.app.contenttypes.presentation.utils.asset import registry_by_name
from nti.app.contenttypes.presentation.utils.asset import get_component_site_name
from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_courses

from nti.app.contenttypes.presentation.views import VIEW_CONTENTS

from nti.app.contenttypes.presentation.views.view_mixins import hexdigest
from nti.app.contenttypes.presentation.views.view_mixins import preflight_input
from nti.app.contenttypes.presentation.views.view_mixins import preflight_mediaroll
from nti.app.contenttypes.presentation.views.view_mixins import preflight_overview_group
from nti.app.contenttypes.presentation.views.view_mixins import preflight_lesson_overview
from nti.app.contenttypes.presentation.views.view_mixins import href_safe_to_external_object

from nti.app.contenttypes.presentation.views.view_mixins import PresentationAssetMixin

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.views.view_mixins import IndexedRequestMixin

from nti.appserver.ugd_edit_views import UGDPutView

from nti.assessment.interfaces import IQPoll
from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQInquiry
from nti.assessment.interfaces import IQAssessment
from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.base._compat import text_

from nti.base.interfaces import DEFAULT_CONTENT_TYPE

from nti.contentfile.interfaces import IContentBaseFile

from nti.contentlibrary.indexed_data import get_site_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.discussions.utils import resolve_discussion_course_bundle

from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.contenttypes.presentation import interface_of_asset

from nti.contenttypes.presentation import AUDIO_MIME_TYPES
from nti.contenttypes.presentation import VIDEO_MIME_TYPES
from nti.contenttypes.presentation import POLL_REF_MIME_TYPES
from nti.contenttypes.presentation import TIMELINE_MIME_TYPES
from nti.contenttypes.presentation import SURVEY_REF_MIME_TYPES
from nti.contenttypes.presentation import TIMELINE_REF_MIME_TYPES
from nti.contenttypes.presentation import ASSIGNMENT_REF_MIME_TYPES
from nti.contenttypes.presentation import SLIDE_DECK_REF_MIME_TYPES
from nti.contenttypes.presentation import QUESTIONSET_REF_MIME_TYPES
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import COURSE_OVERVIEW_GROUP_MIME_TYPES
from nti.contenttypes.presentation import RELATED_WORK_REF_POINTER_MIME_TYPES

from nti.contenttypes.presentation.discussion import is_nti_course_bundle

from nti.contenttypes.presentation.group import DuplicateReference

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIAudioRoll
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import INTIVideoRoll
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTIInquiryRef
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICalendarEventRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import ICoursePresentationAsset
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.interfaces import PresentationAssetCreatedEvent
from nti.contenttypes.presentation.interfaces import WillUpdatePresentationAssetEvent

from nti.contenttypes.presentation.internalization import internalization_ntiaudioref_pre_hook
from nti.contenttypes.presentation.internalization import internalization_ntivideoref_pre_hook

from nti.contenttypes.presentation.utils import create_from_external
from nti.contenttypes.presentation.utils import get_external_pre_hook

from nti.coremetadata.utils import current_principal

from nti.dataserver import authorization as nauth

from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.internalization import notifyModified as notify_modified

from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

from nti.publishing.interfaces import IPublishable

from nti.site.interfaces import IHostPolicyFolder

from nti.site.utils import registerUtility

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE


# POST/PUT views

def principalId():
	try:
		return current_principal(False).id
	except AttributeError:
		return None

def _notify_created(item, principal=None, externalValue=None):
	add_2_connection(item)  # required
	principal = principal or principalId()  # always get a principal
	event_notify(PresentationAssetCreatedEvent(item, principal, externalValue))
	if IPublishable.providedBy(item) and item.is_published():
		item.unpublish(event=False)


def _add_2_course(context, item):
	course = ICourseInstance(context, None)
	if course is not None:
		container = IPresentationAssetContainer(course)
		container[item.ntiid] = item

def _add_2_courses(context, item):
	# We only want to add to our context course, not any subinstances.
	_add_2_course(context, item)

def _add_2_container(context, item):
	result = []
	_add_2_courses(context, item)
	entry = ICourseCatalogEntry(context, None)
	if entry is not None:
		result.append(entry.ntiid)
	return result

def _register_utility(registry, obj=None, provided=None, name=None):
	name = name or obj.ntiid
	registerUtility(registry, obj, provided, name=name)

def _canonicalize(items, creator, base=None, registry=None):
	result = []
	registry = get_site_registry(registry)
	for idx, item in enumerate(items or ()):
		created = True
		provided = interface_of_asset(item)
		if not item.ntiid:
			item.ntiid = make_asset_ntiid(provided, base=base, extra=idx)
		else:
			stored = registry.queryUtility(provided, name=item.ntiid)
			if stored is not None:
				items[idx] = stored
				created = False
		if created:
			result.append(item)
			item.creator = creator  # set creator before notify
			_notify_created(item)
			intid_register(item, registry)
			_register_utility(registry, item, provided, name=item.ntiid)
	return result

def _handle_multipart(context, user, contentObject, sources, provided=None):
	filer = get_course_filer(context, user)
	provided = interface_of_asset(contentObject) if provided is None else provided
	for name, source in sources.items():
		if name in provided:
			# remove existing
			location = getattr(contentObject, name, None)
			if location and is_internal_file_link(location):
				filer.remove(location)
			# save a in a new file
			key = get_safe_source_filename(source, name)
			location = filer.save(key, source,
								  overwrite=False,
								  structure=True,
								  context=contentObject)
			setattr(contentObject, name, location)


class PresentationAssetSubmitViewMixin(PresentationAssetMixin,
									   AbstractAuthenticatedView):

	@Lazy
	def _site_name(self):
		# XXX: use correct registration site
		provided = interface_of_asset(self.context)
		return get_component_site_name(self.context,
							  		   provided,
							  		   name=self.context.ntiid)

	@Lazy
	def _registry(self):
		return registry_by_name(self._site_name)

	@Lazy
	def _course(self):
		result = ICourseInstance(self.context, None)
		return result

	@Lazy
	def _entry(self):
		result = ICourseCatalogEntry(self.context, None)
		return result

	def _get_ntiid(self, item):
		ntiid = item.ntiid
		# Return None for auto-generate NTIIDs
		if 		ntiid \
			and	(INTICourseOverviewGroup.providedBy(item) or IAssetRef.providedBy(item)) \
			and TYPE_UUID in get_specific(ntiid):
			ntiid = None
		return ntiid

	def _check_exists(self, provided, item, creator):
		ntiid = self._get_ntiid(item)
		if ntiid and INTITimeline.providedBy(item):
			# Timelines are the only item we allow to be placed as-is (non-ref).
			pass
		elif ntiid:
			if self._registry.queryUtility(provided, name=ntiid):
				raise hexc.HTTPUnprocessableEntity(_("Asset already exists."))
		else:
			item.ntiid = make_asset_ntiid(provided, extra=self._extra)
		return item

	def _set_creator(self, item, creator):
		creator = getattr(creator, 'username', creator)
		if 		not getattr(item, 'creator', None) \
			or	getattr(item, 'creator', None) == getattr(item, 'byline', None):
			item.creator = creator

	def _handle_package_asset(self, provided, item, creator, extended=None):
		self._set_creator(item, creator)

		# If we don't have parent, use course.
		if item.__parent__ is None:
			item.__parent__ = self._course

		# Don't store in packages; this ensures we index underneath course
		containers = _add_2_container(self._course, item)
		namespace = containers[0] if containers else None
		if provided == INTISlideDeck:
			base = item.ntiid

			# register unique copies
			_canonicalize(item.Slides, creator, base=base, registry=self._registry)
			_canonicalize(item.Videos, creator, base=base, registry=self._registry)

			# add slidedeck ntiid
			item_extended = tuple(extended or ()) + tuple(containers) + (item.ntiid,)

			# register in containers and index
			for x in chain(item.Slides, item.Videos):
				self._set_creator(x, creator)
				_add_2_container(self._course, x)
				self._catalog.index(x, container_ntiids=item_extended,
									namespace=namespace, sites=self._site_name)

		# index item
		item_extended = list(extended or ()) + containers
		self._catalog.index(item, container_ntiids=item_extended,
							namespace=namespace, sites=self._site_name)

	def _handle_docket(self, item):
		# check for contentfiles in icon and href
		for name in ('href', 'icon'):
			name = str(name)
			value = getattr(item, name, None)
			if 		isinstance(value, six.string_types) \
				and (is_valid_ntiid_string(value) or is_internal_file_link(value)):
				if is_valid_ntiid_string(value):
					content_file = find_object_with_ntiid(value)
				else:
					content_file = get_file_from_external_link(value)
				if not IContentBaseFile.providedBy(content_file):
					continue
				external = to_external_file_link(content_file)
				setattr(item, name, external)
				content_file.add_association(item)
				lifecycleevent.modified(content_file)
				if name == 'href':  # update target and type
					item.target = to_external_ntiid_oid(item)  # NTIID
					if INTIRelatedWorkRef.providedBy(item):
						item.type = text_(content_file.contentType)

	def _handle_related_work(self, provided, item, creator, extended=None):
		self._handle_package_asset(provided, item, creator, extended)

		# capture updated/previous data
		# ntiid ends up being the `target`
		ntiid, href = item.target, item.href
		contentType = item.type or text_(DEFAULT_CONTENT_TYPE) # default

		# if client has uploaded a file, capture contentType and target ntiid
		if 		self.request.POST \
			and 'href' in self.request.POST \
			and is_internal_file_link(href):
			filer = get_course_filer(self._course)
			named = filer.get(href) if href else None
			if named is not None:
				ntiid = to_external_ntiid_oid(named)
				contentType = text_(named.contentType or u'') or contentType

		# If we do not have a target, and we have a ContentUnit href, use it.
		if ntiid is None and is_valid_ntiid_string(item.href):
			href_obj = find_object_with_ntiid(item.href)
			if href_obj is not None and IContentUnit.providedBy(href_obj):
				ntiid = item.href

		# parse href
		parsed = urllib_parse.urlparse(href) if href else None
		if ntiid is None and parsed is not None and (parsed.scheme or parsed.netloc):
			# full url
			# XXX not sure how this used
			specific = make_specific_safe(href.lower())
			specific = hexdigest(specific)
			ntiid = make_ntiid(nttype=TYPE_UUID,
							   provider='NTI',
							   specific=specific)

		# replace if needed
		if item.target != ntiid:
			item.target = ntiid
		if item.type != contentType:
			item.type = contentType

		self._handle_docket(item)

	def _handle_timeline(self, provided, item, creator, extended=None):
		self._handle_package_asset(provided, item, creator, extended)
		self._handle_docket(item)

	def _handle_media_roll(self, provided, item, creator, extended=None):
		# set creator
		self._set_creator(item, creator)

		# add to course container
		containers = _add_2_container(self._course, item)

		# register unique copies
		_canonicalize(item.Items or (), creator, base=item.ntiid, registry=self._registry)

		# add media roll ntiid
		item_extended = tuple(extended or ()) + tuple(containers or ()) + (item.ntiid,)
		item_extended = set(item_extended)
		for x in item or ():
			self._set_creator(x, creator)
			_add_2_container(self._course, x)
			self._catalog.index(x, container_ntiids=item_extended, sites=self._site_name)

		# index item
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(item, container_ntiids=item_extended, sites=self._site_name)

	def _handle_group_over_viewable(self, provided, item, creator, extended=None):
		# set creator
		self._set_creator(item, creator)

		# add to course container
		containers = _add_2_container(self._course, item)
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(item, container_ntiids=item_extended, sites=self._site_name)

		if INTIAssessmentRef.providedBy(item):

			# find the target
			if INTIInquiryRef.providedBy(item):
				reference = IQInquiry(item, None)
			else:
				reference = IQAssessment(item, None)
			if reference == None:
				raise hexc.HTTPUnprocessableEntity(
								_('No assessment/inquiry found for given ntiid.'))

			if INTIAssignmentRef.providedBy(item) or INTISurveyRef.providedBy(item):
				item.label = reference.title if not item.label else item.label
				item.title = reference.title if not item.title else item.title
			if INTIQuestionSetRef.providedBy(item) or INTISurveyRef.providedBy(item):
				item.question_count = getattr(reference, 'draw', None) or len(reference)
				item.label = reference.title if not item.label else item.label

			item.containerId = reference.containerId

		elif INTIDiscussionRef.providedBy(item):
			if is_nti_course_bundle(item.target):
				item.id = item.target
				item.target = None
			if not item.isCourseBundle():
				target = find_object_with_ntiid(item.target or '')
				if target is None or not ITopic.providedBy(target):
					raise hexc.HTTPUnprocessableEntity(
								_('No valid topic found for given ntiid.'))
			else:
				resolved = resolve_discussion_course_bundle(self.remoteUser,
															item,
															context=self._course)
				if resolved is not None:  #  (discussion, topic)
					item.target = resolved[1].NTIID

		elif INTICalendarEventRef.providedBy(item):
			target = find_object_with_ntiid(item.target or '')
			# TODO may need to check if the target is within the current course.
			if target is None or not ICourseCalendarEvent.providedBy(target):
				raise hexc.HTTPUnprocessableEntity(
								_('No valid calendar event found for given ntiid.'))


	def _handle_overview_group(self, group, creator, extended=None):
		# set creator
		self._set_creator(group, creator)

		# add to course container
		containers = _add_2_container(self._course, group)

		# have unique copies of group items
		_canonicalize(group.Items, creator, registry=self._registry, base=group.ntiid)

		# include group ntiid in containers
		item_extended = list(extended or ()) + containers + [group.ntiid]
		item_extended = set(item_extended)

		# process group items
		for item in group or ():
			provided = interface_of_asset(item)
			if INTIMediaRoll.providedBy(item):
				self._handle_media_roll(provided, item, creator, item_extended)
			else:
				self._handle_group_over_viewable(provided, item, creator, item_extended)

		# index group
		lesson = group.__parent__
		namespace = to_external_ntiid_oid(lesson) if lesson is not None else None
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(group, container_ntiids=item_extended,
							namespace=namespace, sites=self._site_name)

	def _handle_lesson_overview(self, lesson, creator, extended=None):
		# set creator
		self._set_creator(lesson, creator)

		# add to course container
		containers = _add_2_container(self._course, lesson)

		# Make sure we validate before canonicalize.
		for item in lesson.Items or ():
			self._check_exists(INTICourseOverviewGroup, item, creator)

		# have unique copies of lesson groups
		_canonicalize(lesson.Items, creator, registry=self._registry, base=lesson.ntiid)

		# extend but don't add containers
		item_extended = list(extended or ()) + [lesson.ntiid]

		# process lesson groups
		for group in lesson or ():
			if group.__parent__ is not None and group.__parent__ != lesson:
				msg = _("Overview group has been used by another lesson")
				raise hexc.HTTPUnprocessableEntity(msg)

			# take ownership
			group.__parent__ = lesson
			self._handle_overview_group(group,
										creator=creator,
										extended=item_extended)

		# index lesson item
		namespace = to_external_ntiid_oid(lesson)
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(lesson, container_ntiids=item_extended,
							namespace=namespace, sites=self._site_name)

	def _handle_other_asset(self, provided, item, creator, extended=None):
		containers = _add_2_container(self._course, item)
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(item, container_ntiids=item_extended, sites=self._site_name)

	def _get_slide_deck_for_video(self, item):
		"""
		When inserting a video, iterate through any slide decks looking
		for a collision, if so, we want to index by our slide deck.
		"""
		packages = list(get_course_packages(self._course))
		if packages:
			namespace = [x.ntiid for x in packages]
			target = (item.ntiid,)
			if INTIVideoRef.providedBy(item):
				target = (item.ntiid, getattr(item, 'target', ''))
			catalog = get_library_catalog()
			slide_decks = tuple(catalog.search_objects(provided=INTISlideDeck,
														namespace=namespace,
														sites=self._site_name))
			for slide_deck in slide_decks or ():
				for video in slide_deck.videos or ():
					if video.video_ntiid in target:
						return slide_deck
		return None

	def _handle_video(self, provided, item, creator, extended=None):
		"""
		Check if the given video is actually a slidedeck video and handle
		the slidedeck accordingly.
		"""
		slide_deck = self._get_slide_deck_for_video(item)
		if slide_deck is not None:
			return self._handle_package_asset(INTISlideDeck, slide_deck, creator, extended)
		# Just a video
		if provided == INTIVideo:
			self._handle_package_asset(provided, item, creator, extended)
		else:
			# Video refs need this path
			self._handle_group_over_viewable(provided, item, creator, extended)

	def _handle_asset(self, provided, item, creator, extended=()):
		if INTIRelatedWorkRef.providedBy(item):
			self._handle_related_work(provided, item, creator, extended)
		elif INTITimeline.providedBy(item):
			self._handle_timeline(provided, item, creator, extended)
		elif provided in (INTIVideo, INTIVideoRef):
			self._handle_video(provided, item, creator, extended)
		elif provided in PACKAGE_CONTAINER_INTERFACES:
			self._handle_package_asset(provided, item, creator, extended)
		elif INTIMediaRoll.providedBy(item):
			self._handle_media_roll(provided, item, creator, extended)
		elif IGroupOverViewable.providedBy(item):
			self._handle_group_over_viewable(provided, item, creator, extended)
		elif INTICourseOverviewGroup.providedBy(item):
			self._handle_overview_group(item, creator, extended)
		elif INTILessonOverview.providedBy(item):
			self._handle_lesson_overview(item, creator, extended)
		else:
			self._handle_other_asset(provided, item, creator, extended)
		return item

	def _remove_ntiids(self, ext_obj, do_remove):
		if do_remove:
			ext_obj.pop('ntiid', None)
			ext_obj.pop(NTIID, None)

	def readInput(self, no_ntiids=True):
		result = super(PresentationAssetSubmitViewMixin, self).readInput()
		self._remove_ntiids(result, no_ntiids)
		return result

	def transformOutput(self, obj):
		provided = interface_of_asset(obj)
		if provided is not None and 'href' in provided:
			result = href_safe_to_external_object(obj)
		else:
			result = obj
		return result


#TODO this doesn't belong on the ICourseCatalogEntry.
#Consider moving to ICoursePresentationAssets
@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=ICoursePresentationAssets,
			 request_method='POST',
			 permission=nauth.ACT_CONTENT_EDIT)
class PresentationAssetPostView(PresentationAssetSubmitViewMixin,
								ModeledContentUploadRequestUtilsMixin):  # order matters

	content_predicate = IPresentationAsset.providedBy

	@Lazy
	def _site_name(self):
		folder = find_interface(self._course, IHostPolicyFolder, strict=False)
		return folder.__name__

	def checkContentObject(self, contentObject, externalValue):
		if contentObject is None or not self.content_predicate(contentObject):
			transaction.doom()
			logger.debug("Failing to POST: input of unsupported/missing Class: %s => %s",
						 externalValue, contentObject)
			raise hexc.HTTPUnprocessableEntity(_('Unsupported/missing Class'))
		return contentObject

	def parseInput(self, creator, search_owner=False, externalValue=None):
		# process input
		externalValue = self.readInput() if not externalValue else externalValue
		externalValue = preflight_input(externalValue, self.request)
		result = copy.deepcopy(externalValue)  # return original input
		# create and validate
		contentObject = create_from_external(externalValue, notify=False)
		contentObject = self.checkContentObject(contentObject, externalValue)
		# update with external
		self.updateContentObject(contentObject, externalValue, set_id=True, notify=False)
		# set creator
		self._set_creator(contentObject, creator)
		return contentObject, result

	def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
		contentObject, externalValue = self.parseInput(creator, search_owner, externalValue)
		sources = get_all_sources(self.request)
		return contentObject, externalValue, sources

	def _do_call(self):
		creator = self.remoteUser
		contentObject, externalValue, sources = self.readCreateUpdateContentObject(creator)
		contentObject.creator = creator.username  # use string
		provided = interface_of_asset(contentObject)

		# check item does not exists and notify
		self._check_exists(provided, contentObject, creator)

		# add to connection and register
		intid_register(contentObject, registry=self._registry)
		_register_utility(self._registry,
						  obj=contentObject,
						  provided=provided,
						  name=contentObject.ntiid)

		# handle multi-part data
		if sources:
			validate_sources(self.remoteUser, contentObject, sources)
			_handle_multipart(self._course, self.remoteUser, contentObject, sources)

		self.request.response.status_int = 201
		self._handle_asset(provided, contentObject, creator.username)

		# notify when object is ready
		_notify_created(contentObject, self.remoteUser.username, externalValue)
		return self.transformOutput(contentObject)

# put views

@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='PUT',
			   permission=nauth.ACT_CONTENT_EDIT)
class PresentationAssetPutView(PresentationAssetSubmitViewMixin,
							   UGDPutView):  # order matters

	def preflight(self, contentObject, externalValue):
		preflight_input(externalValue, self.request)

	def postflight(self, updatedObject, externalValue, preflight=None):
		return None

	def updateContentObject(self, contentObject, externalValue, set_id=False, notify=True):
		data = self.preflight(contentObject, externalValue)
		originalSource = copy.deepcopy(externalValue)
		pre_hook = get_external_pre_hook(externalValue)

		event_notify(WillUpdatePresentationAssetEvent(contentObject,
													  self.remoteUser,
													  externalValue))

		result = UGDPutView.updateContentObject(self,
												contentObject,
												externalValue,
												set_id=set_id,
												notify=False,
												pre_hook=pre_hook)
		sources = get_all_sources(self.request)
		if sources:
			courses = get_presentation_asset_courses(self.context) or (self._course,)
			validate_sources(self.remoteUser, result, sources)
			_handle_multipart(next(iter(courses)),
							  self.remoteUser,
							  self.context,
							  sources)

		self.postflight(contentObject, externalValue, data)
		notify_modified(contentObject, originalSource)
		return result

	def _get_containers(self):
		result = []
		for iface in (INTICourseOverviewGroup, INTILessonOverview):
			parent = find_interface(self.context, iface, strict=False)
			if parent is not None:
				result.append(parent)
		return result

	def __call__(self):
		result = UGDPutView.__call__(self)
		containers = self._get_containers()
		self._handle_asset(interface_of_asset(result), result,
						   result.creator, containers)
		return self.transformOutput(result)

@view_config(context=IPackagePresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='PUT',
			   permission=nauth.ACT_CONTENT_EDIT)
class PackagePresentationAssetPutView(PresentationAssetPutView):

	@Lazy
	def _site_name(self):
		folder = find_interface(self.context, IHostPolicyFolder, strict=False)
		if folder is None:
			result = super(PackagePresentationAssetPutView, self)._site_name
		else:
			result = folder.__name__
		return result

	@Lazy
	def _course(self):
		result = find_interface(self.context, ICourseInstance, strict=False)
		if result is not None:  # direct check in case course w/ no pkg
			return result
		package = find_interface(self.context, IContentPackage, strict=False)
		if package is not None:
			courses = get_courses_for_packages(package.ntiid)
			result = courses[0] if courses else None  # should always find one
		return result


@view_config(context=INTIMedia)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='PUT',
			   permission=nauth.ACT_CONTENT_EDIT)
class MediaAssetPutView(PackagePresentationAssetPutView):

	def readInput(self, no_ntiids=True):
		result = PackagePresentationAssetPutView.readInput(self, no_ntiids)
		result.pop('transcripts', None)
		return result


@view_config(context=ICoursePresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='PUT',
			   permission=nauth.ACT_CONTENT_EDIT)
class CoursePresentationAssetPutView(PresentationAssetPutView):

	@Lazy
	def _site_name(self):
		folder = find_interface(self.context, IHostPolicyFolder, strict=False)
		return folder.__name__

	@Lazy
	def _course(self):
		course = find_interface(self.context, ICourseInstance, strict=False)
		return course

@view_config(context=INTILessonOverview)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='PUT',
			   permission=nauth.ACT_CONTENT_EDIT)
class LessonOverviewPutView(PresentationAssetPutView):

	def preflight(self, contentObject, externalValue):
		preflight_lesson_overview(externalValue, self.request)
		data = {x.ntiid:x for x in contentObject}  # save groups
		return data

	def _get_containers(self):
		return ()

	def postflight(self, updatedObject, externalValue, preflight):
		updated = {x.ntiid for x in updatedObject}
		for ntiid, group in preflight.items():
			if ntiid not in updated:  # group removed
				remove_presentation_asset(group, self._registry, self._catalog)

@view_config(context=INTICourseOverviewGroup)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='PUT',
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseOverviewGroupPutView(PresentationAssetPutView):

	def preflight(self, contentObject, externalValue):
		preflight_overview_group(externalValue, self.request)
		data = {x.ntiid:x for x in contentObject}
		return data

	def _get_containers(self):
		lesson = find_interface(self.context, INTILessonOverview, strict=False)
		if lesson:
			return (lesson.ntiid,)
		return ()

	def postflight(self, updatedObject, externalValue, preflight):
		updated = {x.ntiid for x in updatedObject}
		for ntiid, item in preflight.items():
			if ntiid not in updated:  # ref removed
				remove_presentation_asset(item, self._registry, self._catalog)

@view_config(context=INTIAudioRoll)
@view_config(context=INTIVideoRoll)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='PUT',
			   permission=nauth.ACT_CONTENT_EDIT)
class MediaRollPutView(PresentationAssetPutView):

	def preflight(self, contentObject, externalValue):
		preflight_mediaroll(externalValue, self.request)
		data = {x.ntiid:x for x in contentObject}
		return data

	def postflight(self, updatedObject, externalValue, preflight):
		updated = {x.ntiid for x in updatedObject}
		for ntiid, item in preflight.items():
			if ntiid not in updated:  # ref removed
				remove_presentation_asset(item, self._registry, self._catalog)


# ordered contents


@view_config(context=INTILessonOverview)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name=VIEW_CONTENTS,
			   permission=nauth.ACT_CONTENT_EDIT)
class LessonOverviewOrderedContentsView(PresentationAssetSubmitViewMixin,
										ModeledContentUploadRequestUtilsMixin,
										IndexedRequestMixin):  # order matters

	content_predicate = INTICourseOverviewGroup.providedBy

	def checkContentObject(self, contentObject, externalValue):
		if contentObject is None or not self.content_predicate(contentObject):
			transaction.doom()
			logger.debug("Failing to POST: input of unsupported/missing Class: %s => %s",
						 externalValue, contentObject)
			raise hexc.HTTPUnprocessableEntity(_('Unsupported/missing Class'))
		return contentObject

	def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
		# process input
		externalValue = self.readInput() if not externalValue else externalValue
		if MIMETYPE not in externalValue:
			externalValue[MIMETYPE] = COURSE_OVERVIEW_GROUP_MIME_TYPES[0]
		externalValue = preflight_input(externalValue, self.request)
		result = copy.deepcopy(externalValue)  # return original input
		# create object
		contentObject = create_from_external(externalValue, notify=False)
		contentObject = self.checkContentObject(contentObject, externalValue)
		# set creator
		self._set_creator(contentObject, creator)
		return contentObject, result

	def _do_call(self):
		index = self._get_index()
		creator = self.remoteUser
		provided = INTICourseOverviewGroup
		contentObject, externalValue = self.readCreateUpdateContentObject(creator)

		# set lineage
		contentObject.__parent__ = self.context

		# check item does not exists and notify
		self._check_exists(provided, contentObject, creator)

		# add to connection and register
		intid_register(contentObject, registry=self._registry)
		_register_utility(self._registry,
						  provided=provided,
						  obj=contentObject,
						  name=contentObject.ntiid)

		self._handle_overview_group(contentObject,
									creator=creator,
									extended=(self.context.ntiid,))
		_notify_created(contentObject, self.remoteUser.username, externalValue)

		# insert in context, lock and notify
		self.context.insert(index, contentObject)
		self.context.childOrderLock()
		notify_modified(self.context, externalValue, external_keys=(ITEMS,))

		self.request.response.status_int = 201
		return contentObject

@view_config(context=INTICourseOverviewGroup)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name=VIEW_CONTENTS,
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseOverviewGroupInsertView(PresentationAssetSubmitViewMixin,
									ModeledContentUploadRequestUtilsMixin,
									IndexedRequestMixin):  # order matters
	"""
	We accept asset items by index here. We handle two types specially here:

	We turn media, timeline, and slidedecks into refs here, given an NTIID.
	"""

	content_predicate = IGroupOverViewable.providedBy

	def _remove_ntiids(self, ext_obj, do_remove):
		# Do not remove our media ntiids, these will be our ref targets.
		# If we don't have a mimeType, we need the ntiid to fetch the (video) object.
		mimeType = ext_obj.get(MIMETYPE) or ext_obj.get('mimeType')
		is_media = bool(mimeType in VIDEO_MIME_TYPES or mimeType in AUDIO_MIME_TYPES)
		if mimeType and not is_media and mimeType not in TIMELINE_MIME_TYPES:
			super(CourseOverviewGroupInsertView, self)._remove_ntiids(ext_obj, do_remove)

	def _do_preflight_input(self, externalValue):
		"""
		Swizzle media into refs for overview groups. If we're missing a mimetype, the given
		ntiid *must* resolve to a video/timeline. All other types should be fully defined (ref) objects.
		"""
		if isinstance(externalValue, Mapping) and MIMETYPE not in externalValue:
			ntiid = externalValue.get('ntiid') or externalValue.get(NTIID)
			__traceback_info__ = ntiid
			if not ntiid:
				raise hexc.HTTPUnprocessableEntity(_('Missing overview group item NTIID'))

			resolved = find_object_with_ntiid(ntiid)
			if resolved is None:
				raise hexc.HTTPUnprocessableEntity(_('Missing overview group item'))

			if 		INTISlideDeck.providedBy(resolved) \
				or	INTISlideDeckRef.providedBy(resolved):
				externalValue[MIMETYPE] = SLIDE_DECK_REF_MIME_TYPES[0]  # make a ref always
			# timelines
			elif 	INTITimeline.providedBy(resolved) \
				or	INTITimelineRef.providedBy(resolved):
				externalValue[MIMETYPE] = TIMELINE_REF_MIME_TYPES[0]  # make a ref always
			# relatedwork refs
			elif 	INTIRelatedWorkRef.providedBy(resolved) \
				or	INTIRelatedWorkRefPointer.providedBy(resolved):
				externalValue[MIMETYPE] = RELATED_WORK_REF_POINTER_MIME_TYPES[0]  # make a ref always
			# media objects
			elif	INTIMedia.providedBy(resolved) \
				or	INTIMediaRef.providedBy(resolved):
				externalValue[MIMETYPE] = resolved.mimeType
			# assignment objects
			elif	IQAssignment.providedBy(resolved) \
				or	INTIAssignmentRef.providedBy(resolved):
				externalValue[MIMETYPE] = ASSIGNMENT_REF_MIME_TYPES[0]
			# poll objects
			elif	IQPoll.providedBy(resolved) \
				or	INTIPollRef.providedBy(resolved):
				externalValue[MIMETYPE] = POLL_REF_MIME_TYPES[0]
			# survey objects
			elif	IQSurvey.providedBy(resolved) \
				or	INTISurveyRef.providedBy(resolved):
				externalValue[MIMETYPE] = SURVEY_REF_MIME_TYPES[0]
			# question sets
			elif	IQuestionSet.providedBy(resolved) \
				or	INTIQuestionSetRef.providedBy(resolved):
				externalValue[MIMETYPE] = QUESTIONSET_REF_MIME_TYPES[0]
			else:
				# We did not have a mimetype, and we have an ntiid the resolved
				# into an unexpected type; blow chunks.
				raise hexc.HTTPUnprocessableEntity(_('Invalid overview group item'))

		mimeType = externalValue.get(MIMETYPE) or externalValue.get('mimeType')
		if mimeType in VIDEO_MIME_TYPES or mimeType in AUDIO_MIME_TYPES:
			if isinstance(externalValue, Mapping):
				internalization_ntiaudioref_pre_hook(None, externalValue)
				internalization_ntivideoref_pre_hook(None, externalValue)
		return preflight_input(externalValue, self.request)

	def checkContentObject(self, contentObject, externalValue):
		if contentObject is None or not self.content_predicate(contentObject):
			transaction.doom()
			logger.debug("Failing to POST: input of unsupported/missing Class: %s => %s",
						 externalValue, contentObject)
			raise hexc.HTTPUnprocessableEntity(_('Unsupported/missing Class'))
		return contentObject

	def parseInput(self, creator, search_owner=False, externalValue=None):
		external_input = self.readInput() if not externalValue else externalValue
		externalValue = self._do_preflight_input(external_input)
		external_input = copy.deepcopy(external_input)  # return original input
		if isinstance(externalValue, Mapping):
			contentObject = create_from_external(externalValue, notify=False)
			contentObject = self.checkContentObject(contentObject, externalValue)
			self._set_creator(contentObject, creator)
		else:
			contentObject = externalValue
		return contentObject, external_input

	def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
		contentObject, externalValue = self.parseInput(creator, search_owner, externalValue)
		return contentObject, externalValue

	def _convert_timeline_to_timelineref(self, timeline, creator, extended, externalValue):
		"""
		Convert and create a timeline ref that can be stored in our overview group.
		"""
		timeline_ref = INTITimelineRef(timeline)
		intid_register(timeline_ref, registry=self._registry)
		self._finish_creating_object(timeline_ref, creator, extended, INTITimelineRef, externalValue)
		return timeline_ref

	def _convert_relatedwork_to_pointer(self, relatedwork, creator, extended, externalValue):
		"""
		Convert and create a relatedwork ref that can be stored in our overview group.
		"""
		asset_ref = INTIRelatedWorkRefPointer(relatedwork)
		intid_register(asset_ref, registry=self._registry)
		self._finish_creating_object(asset_ref, creator, extended, INTIRelatedWorkRefPointer, externalValue)
		return asset_ref

	def _finish_creating_object(self, obj, creator, extended, provided, externalValue):
		"""
		Finish creating our object by firing events, registering, etc.
		"""
		_register_utility(self._registry,
						  provided=provided,
						  obj=obj,
						  name=obj.ntiid)
		self._handle_asset(provided,
						   obj,
						   creator=creator,
						   extended=extended)
		if obj.__parent__ is None:
			# We always take ownership when inserting into group anyway
			# Take ownership before sending event
			obj.__parent__ = self.context
		_notify_created(obj, self.remoteUser.username, externalValue)

	def _do_call(self):
		index = self._get_index()
		creator = self.remoteUser
		contentObject, externalValue = self.readCreateUpdateContentObject(creator)
		provided = interface_of_asset(contentObject)
		__traceback_info__ = contentObject

		# check item does not exists and notify
		self._check_exists(provided, contentObject, creator)
		# set creator
		self._set_creator(contentObject, creator)
		# Must have intid before doing multipart (as we setup weak refs).
		intid_register(contentObject, registry=self._registry)

		# XXX: Multi-part data must be done after the object has been registered
		# with the InitId facility in order to set file associations
		sources = get_all_sources(self.request)
		if sources: # multi-part data
			validate_sources(self.remoteUser, contentObject, sources)
			_handle_multipart(self._course, self.remoteUser, contentObject, sources)

		parent = self.context.__parent__
		extended = (self.context.ntiid,) + ((parent.ntiid,) if parent is not None else ())

		self._finish_creating_object(contentObject, creator, extended, provided, externalValue)

		if INTITimeline.providedBy(contentObject):
			contentObject = self._convert_timeline_to_timelineref(contentObject, creator,
																  extended, externalValue)
		elif INTIRelatedWorkRef.providedBy(contentObject):
			contentObject = self._convert_relatedwork_to_pointer(contentObject, creator,
																 extended, externalValue)

		try:
			self.context.insert(index, contentObject)
		except DuplicateReference:
			raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Reference already exists in section."),
                                 'code': u'ReferenceAlreadyExistsError'
                             },
                             None)

		notify_modified(self.context, externalValue, external_keys=(ITEMS,))
		self.request.response.status_int = 201
		self.context.childOrderLock()

		# We don't return refs in the overview group; so don't here either.
		contentObject = IConcreteAsset(contentObject, contentObject)
		return self.transformOutput(contentObject)
