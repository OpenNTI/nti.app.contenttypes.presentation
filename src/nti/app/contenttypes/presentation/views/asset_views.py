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
import uuid
from itertools import chain
from urlparse import urlparse
from collections import Mapping

import transaction

from zope import interface

from zope.component.hooks import getSite

from zope.event import notify

from zope.security.interfaces import NoInteraction
from zope.security.management import getInteraction

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from pyramid.threadlocal import get_current_request

from nti.app.renderers.interfaces import INoHrefInResponse

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import get_safe_source_filename
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile import validate_sources

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.utils import component_site
from nti.app.contenttypes.presentation.utils import intid_register
from nti.app.contenttypes.presentation.utils import add_2_connection
from nti.app.contenttypes.presentation.utils import make_asset_ntiid
from nti.app.contenttypes.presentation.utils import registry_by_name
from nti.app.contenttypes.presentation.utils import remove_presentation_asset
from nti.app.contenttypes.presentation.utils import get_presentation_asset_courses
from nti.app.contenttypes.presentation.utils import resolve_discussion_course_bundle

from nti.app.contenttypes.presentation.views import VIEW_ASSETS
from nti.app.contenttypes.presentation.views import VIEW_CONTENTS
from nti.app.contenttypes.presentation.views import VIEW_NODE_MOVE

from nti.app.contenttypes.presentation.views.view_mixins import hexdigest
from nti.app.contenttypes.presentation.views.view_mixins import NTIIDPathMixin
from nti.app.contenttypes.presentation.views.view_mixins import IndexedRequestMixin
from nti.app.contenttypes.presentation.views.view_mixins import AbstractChildMoveView
from nti.app.contenttypes.presentation.views.view_mixins import PublishVisibilityMixin

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware import ASSETS_FOLDER
from nti.app.products.courseware import VIEW_RECURSIVE_AUDIT_LOG
from nti.app.products.courseware import VIEW_RECURSIVE_TX_HISTORY

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.views.view_mixins import AbstractRecursiveTransactionHistoryView

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.assessment.interfaces import IQInquiry
from nti.assessment.interfaces import IQAssessment

from nti.common.maps import CaseInsensitiveDict

from nti.common.property import Lazy

from nti.coremetadata.interfaces import IPublishable

from nti.contentlibrary.indexed_data import get_site_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation import AUDIO_MIMETYES
from nti.contenttypes.presentation import VIDEO_MIMETYES
from nti.contenttypes.presentation import TIMELINE_MIMETYES
from nti.contenttypes.presentation import LESSON_OVERVIEW_MIMETYES
from nti.contenttypes.presentation import ALL_MEDIA_ROLL_MIME_TYPES
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import COURSE_OVERVIEW_GROUP_MIMETYES

from nti.contenttypes.presentation.discussion import is_nti_course_bundle

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIAudioRoll
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import INTIVideoRoll
from nti.contenttypes.presentation.interfaces import INTIInquiryRef
from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import ICoursePresentationAsset
from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.interfaces import OverviewGroupMovedEvent
from nti.contenttypes.presentation.interfaces import PresentationAssetMovedEvent
from nti.contenttypes.presentation.interfaces import PresentationAssetCreatedEvent

from nti.contenttypes.presentation.internalization import internalization_ntiaudioref_pre_hook
from nti.contenttypes.presentation.internalization import internalization_ntivideoref_pre_hook

from nti.contenttypes.presentation.utils import create_from_external
from nti.contenttypes.presentation.utils import get_external_pre_hook

from nti.dataserver import authorization as nauth

from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import StandardExternalFields

from nti.externalization.internalization import notify_modified

from nti.externalization.oids import to_external_ntiid_oid

from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE

# GET views

@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_READ,
			   request_method='GET')
class PresentationAssetGetView(GenericGetView, PublishVisibilityMixin):

	def __call__(self):
		accept = self.request.headers.get(b'Accept') or u''
		if accept == 'application/vnd.nextthought.pageinfo+json':
			raise hexc.HTTPNotAcceptable()
		if not self._is_visible(self.context):
			raise hexc.HTTPForbidden(_("Item not visible."))
		result = GenericGetView.__call__(self)
		return result

@view_config(context=INTITimeline)
@view_config(context=INTIRelatedWorkRef)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_READ,
			   request_method='GET')
class NoHrefAssetGetView(PresentationAssetGetView):

	def __call__(self):
		result = PresentationAssetGetView.__call__(self)
		result = to_external_object(result)
		interface.alsoProvides(result, INoHrefInResponse)
		return result

@view_config(context=INTIDiscussionRef)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_READ,
			   request_method='GET')
class DiscussionRefGetView(AbstractAuthenticatedView, PublishVisibilityMixin):

	def __call__(self):
		accept = self.request.headers.get(b'Accept') or u''
		if accept == 'application/vnd.nextthought.discussionref':
			if not self._is_visible(self.context):
				raise hexc.HTTPForbidden(_("Item not visible."))
			return self.context
		elif self.context.isCourseBundle():
			course = ICourseInstance(self.context)
			resolved = resolve_discussion_course_bundle(user=self.remoteUser,
														item=self.context,
														context=course)
			if resolved is not None:
				cdiss, topic = resolved
				logger.debug('%s resolved to %s', self.context.id, cdiss)
				return topic
			else:
				raise hexc.HTTPNotFound(_("Topic not found."))
		else:
			raise hexc.HTTPNotAcceptable()

@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_READ,
			   request_method='GET',
			   name="schema")
class PresentationAssetSchemaView(AbstractAuthenticatedView):

	def __call__(self):
		result = self.context.schema()
		return result

# POST/PUT views

def principalId():
	try:
		return getInteraction().participations[0].principal.id
	except (NoInteraction, IndexError, AttributeError):
		return None

def _notify_created(item, principal=None, externalValue=None):
	add_2_connection(item)  # required
	principal = principal or principalId()  # always get a principal
	notify(PresentationAssetCreatedEvent(item, principal, externalValue))
	if IPublishable.providedBy(item) and item.is_published():
		item.unpublish()

def _add_2_packages(context, item):
	result = []
	for package in get_course_packages(context):
		container = IPresentationAssetContainer(package)
		container[item.ntiid] = item
		result.append(package.ntiid)
	return result

def _add_2_course(context, item):
	course = ICourseInstance(context, None)
	if course is not None:
		container = IPresentationAssetContainer(course, None)
		container[item.ntiid] = item

def _add_2_courses(context, item):
	_add_2_course(context, item)
	for subinstance in get_course_subinstances(context):
		_add_2_course(subinstance, item)

def _add_2_container(context, item, packages=False):
	result = []
	_add_2_courses(context, item)
	if packages:
		result.extend(_add_2_packages(context, item))
	entry = ICourseCatalogEntry(context, None)
	if entry is not None:
		result.append(entry.ntiid)
	return result

def _canonicalize(items, creator, base=None, registry=None):
	result = []
	registry = get_site_registry(registry)
	for idx, item in enumerate(items or ()):
		created = True
		provided = iface_of_asset(item)
		if not item.ntiid:
			item.ntiid = make_asset_ntiid(provided, creator, base=base, extra=idx)
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
			registerUtility(registry, item, provided, name=item.ntiid)
	return result

def _handle_multipart(context, user, contentObject, sources, provided=None):
	filer = get_course_filer(context, user)
	provided = iface_of_asset(contentObject) if provided is None else provided
	for name, source in sources.items():
		if name in provided:
			# remove existing
			location = getattr(contentObject, name, None)
			if location:
				filer.remove(location)
			# save a in a new file
			key = get_safe_source_filename(source, name)
			location = filer.save(key, source, overwrite=False,
								  bucket=ASSETS_FOLDER, context=contentObject)
			setattr(contentObject, name, location)

@view_config(route_name='objects.generic.traversal',
			 request_method='POST',
			 context=INTILessonOverview,
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name=VIEW_NODE_MOVE)
class LessonOverviewMoveView(AbstractChildMoveView):
	"""
	Move the given object between lessons or overview groups. For
	overview groups, we need to resolve the given ntiid as an
	asset ref in the old parent (or new parent if moving internally).

	:raises HTTPUnprocessableEntity if we do not find the given ntiid
		underneath the old parent
	"""

	notify_type = None

	def _get_context_ntiid(self):
		return self.context.ntiid

	def _remove_from_parent(self, parent, obj):
		return parent.remove(obj)

	def _get_children_ntiids(self, parent_ntiid):
		result = set()
		result.add(parent_ntiid)
		def _recur(node):
			val = getattr(node, 'ntiid', None)
			if val:
				result.add(val)
			try:
				for child in node.Items or ():
					_recur(child)
			except AttributeError:
				pass

		_recur(self.context)
		return result

	def _get_ref_in_parent(self, ntiid, parent):
		# XXX: If the client were to pass us OIDs (to the refs),
		# this code could disappear.
		# Assuming one hit per parent...We actually ensure
		# that in the group itself (only for videos).
		for child in list(parent):
			# We want to move the actual ref, but clients will
			# only send target ntiids.
			if 		ntiid == getattr(child, 'target', '') \
				or 	ntiid == getattr(child, 'ntiid', ''):
				return child
		return None

	def _set_notify_type(self, obj):
		if INTICourseOverviewGroup.providedBy( obj ):
			self.notify_type = OverviewGroupMovedEvent
		else:
			self.notify_type = PresentationAssetMovedEvent

	def _get_object_to_move(self, ntiid, old_parent=None):
		if old_parent is not None:
			# Need a to convert any non-ref into the ref.
			obj = self._get_ref_in_parent(ntiid, old_parent)
			if obj is None:
				raise hexc.HTTPUnprocessableEntity(_('No ref found for given media ntiid.'))
		self._set_notify_type( obj )
		return obj

class PresentationAssetMixin(object):

	@Lazy
	def _site_name(self):
		return getSite().__name__

	@Lazy
	def _catalog(self):
		return get_library_catalog()

	@Lazy
	def _extra(self):
		return str(uuid.uuid4()).split('-')[0]

	@Lazy
	def _registry(self):
		return get_site_registry()

class PresentationAssetSubmitViewMixin(PresentationAssetMixin,
									   AbstractAuthenticatedView):

	@Lazy
	def _site_name(self):
		# XXX: use correct registration site
		provided = iface_of_asset(self.context)
		return component_site(self.context,
							  provided=provided,
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
		if ntiid and INTITimeline.providedBy( item ):
			# Timelines are the only item we allow to be placed as-is (non-ref).
			pass
		elif ntiid:
			if self._registry.queryUtility(provided, name=ntiid):
				raise hexc.HTTPUnprocessableEntity(_("Asset already exists."))
		else:
			item.ntiid = make_asset_ntiid(provided, creator, extra=self._extra)
		return item

	def _set_creator(self, item, creator):
		creator = getattr(creator, 'username', creator)
		if 		not getattr(item, 'creator', None) \
			or	getattr(item, 'creator', None) == getattr(item, 'byline', None):
			item.creator = creator

	def _handle_package_asset(self, provided, item, creator, extended=None):
		self._set_creator(item, creator)

		packages = list(get_course_packages(self._course))
		# Set lineage; prefer package, but fall back to group.
		item.__parent__ = packages[0] if packages else getattr( item, '__parent__', None )

		containers = _add_2_container(self._course, item, packages=True)
		namespace = containers[0] if containers else None  # first pkg
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
				_add_2_container(self._course, x, packages=True)
				self._catalog.index(x, container_ntiids=item_extended,
									namespace=namespace, sites=self._site_name)

		# index item
		item_extended = list(extended or ()) + containers
		self._catalog.index(item, container_ntiids=item_extended,
							namespace=namespace, sites=self._site_name)

	def _handle_related_work(self, provided, item, creator, extended=None):
		self._set_creator(item, creator)
		self._handle_package_asset(provided, item, creator, extended)

		# capture updated/previous data
		ntiid, href = item.target, item.href
		contentType = item.type or u'application/octet-stream'  # default

		# if client has uploaded a file, capture contentType and target ntiid
		if self.request.POST and 'href' in self.request.POST:
			filer = get_course_filer(self._course)
			named = filer.get(href) if href else None
			if named is not None:
				ntiid = to_external_ntiid_oid(named)
				contentType = unicode(named.contentType or u'') or contentType

		# If we do not have a target, and we have a ContentUnit href, use it.
		if ntiid is None and is_valid_ntiid_string( item.href ):
			href_obj = find_object_with_ntiid( item.href )
			if href_obj is not None and IContentUnit.providedBy( href_obj ):
				ntiid = item.href

		# parse href
		parsed = urlparse(href) if href else None
		if ntiid is None and parsed is not None and (parsed.scheme or parsed.netloc):  # full url
			ntiid = make_ntiid(nttype=TYPE_UUID,
							   provider='NTI',
							   specific=hexdigest(href.lower()))

		# replace if needed
		if item.target != ntiid:
			item.target = ntiid
		if item.type != contentType:
			item.type = contentType

	def _handle_media_roll(self, provided, item, creator, extended=None):
		# set creator
		self._set_creator(item, creator)

		# add to course container
		containers = _add_2_container(self._course, item, packages=False)

		# register unique copies
		_canonicalize(item.Items or (), creator, base=item.ntiid, registry=self._registry)

		# add media roll ntiid
		item_extended = tuple(extended or ()) + tuple(containers or ()) + (item.ntiid,)
		item_extended = set(item_extended)
		for x in item or ():
			self._set_creator(x, creator)
			_add_2_container(self._course, x, packages=False)
			self._catalog.index(x, container_ntiids=item_extended, sites=self._site_name)

		# index item
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(item, container_ntiids=item_extended, sites=self._site_name)

	def _handle_group_over_viewable(self, provided, item, creator, extended=None):
		# set creator
		self._set_creator(item, creator)

		# add to course container
		containers = _add_2_container(self._course, item, packages=False)
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

			if INTIAssignmentRef.providedBy(item):
				item.label = reference.title if not item.label else item.label
				item.title = reference.title if not item.title else item.title
			elif INTIQuestionSetRef.providedBy(item) or INTISurveyRef.providedBy(item):
				item.question_count = len(reference)
				item.label = reference.title if not item.label else item.label

			# set container id
			if reference.__parent__ is not None:
				item.containerId = reference.__parent__.ntiid

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
				if resolved is not None:
					_, topic = resolved
					item.target = topic.NTIID

	def _handle_overview_group(self, group, creator, extended=None):
		# set creator
		self._set_creator(group, creator)

		# add to course container
		containers = _add_2_container(self._course, group, packages=False)

		# have unique copies of group items
		_canonicalize(group.Items, creator, registry=self._registry, base=group.ntiid)

		# include group ntiid in containers
		item_extended = list(extended or ()) + containers + [group.ntiid]
		item_extended = set(item_extended)

		# process group items
		for item in group or ():
			provided = iface_of_asset(item)
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
		containers = _add_2_container(self._course, lesson, packages=False)

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
		containers = _add_2_container(self._course, item, packages=False)
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
			if INTIVideoRef.providedBy( item ):
				target = (item.ntiid, getattr( item, 'target', '' ))
			catalog = get_library_catalog()
			slide_decks = tuple( catalog.search_objects( provided=INTISlideDeck,
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
		slide_deck = self._get_slide_deck_for_video( item )
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
		provided = iface_of_asset(obj)
		if provided is not None and 'href' in provided:
			result = to_external_object(obj)
			interface.alsoProvides(result, INoHrefInResponse)
		else:
			result = obj
		return result

# preflight routines
MAX_TITLE_LENGTH = 300

def _validate_input(externalValue):
	# Normally, we'd let our defined schema enforce limits,
	# but old, unreasonable content makes us enforce some
	# limits here, through the user API.
	for attr in ('title', 'Title', 'label', 'Label'):
		value = externalValue.get(attr)
		if value and len(value) > MAX_TITLE_LENGTH:
			# Mapping to what we do in nti.schema.field.
			raise_json_error(get_current_request(),
							 hexc.HTTPUnprocessableEntity,
							 {
							 	u'provided_size': len(value),
							 	u'max_size': MAX_TITLE_LENGTH,
								u'message': _('${field} is too long. ${max_size} character limit.',
											mapping={'field': attr.capitalize(),
													'max_size': MAX_TITLE_LENGTH}),
								u'code': 'TooLong',
								u'field': attr.capitalize()
							 },
							 None)

def preflight_mediaroll(externalValue):
	if not isinstance(externalValue, Mapping):
		return externalValue

	items = externalValue.get(ITEMS)

	_validate_input(externalValue)
	for idx, item in enumerate(items or ()):
		if isinstance(item, six.string_types):
			item = items[idx] = {'ntiid': item}
		if isinstance(item, Mapping) and MIMETYPE not in item:
			ntiid = item.get('ntiid') or item.get(NTIID)
			__traceback_info__ = ntiid
			if not ntiid:
				raise hexc.HTTPUnprocessableEntity(_('Missing media roll item NTIID'))
			resolved = find_object_with_ntiid(ntiid)
			if resolved is None:
				raise hexc.HTTPUnprocessableEntity(_('Missing media roll item'))
			if (INTIMedia.providedBy(resolved) or INTIMediaRef.providedBy(resolved)):
				item[MIMETYPE] = resolved.mimeType
			else:
				raise hexc.HTTPUnprocessableEntity(_('Invalid media roll item'))
	# If they're editing a field, make sure we have a mimetype
	# so our pre-hooks fire.
	# TOOD: Do we need to do this elsewhere?
	if MIMETYPE not in externalValue:
		externalValue[MIMETYPE] = "application/vnd.nextthought.ntivideoroll"
	return externalValue

def preflight_overview_group(externalValue):
	if not isinstance(externalValue, Mapping):
		return externalValue

	_validate_input(externalValue)
	items = externalValue.get(ITEMS)
	for idx, item in enumerate(items or ()):
		if isinstance(item, six.string_types):
			item = items[idx] = {'ntiid': item}
		if isinstance(item, Mapping) and MIMETYPE not in item:
			ntiid = item.get('ntiid') or item.get(NTIID)
			__traceback_info__ = ntiid
			if not ntiid:
				raise hexc.HTTPUnprocessableEntity(_('Missing overview group item NTIID'))
			resolved = find_object_with_ntiid(ntiid)
			if resolved is None:
				raise hexc.HTTPUnprocessableEntity(_('Missing overview group item'))
			if not IGroupOverViewable.providedBy(resolved):
				logger.warn("Coercing %s,%s into overview group", resolved.mimeType, ntiid)
			item[MIMETYPE] = resolved.mimeType
		else:
			preflight_input(item)

	return externalValue

def preflight_lesson_overview(externalValue):
	if not isinstance(externalValue, Mapping):
		return externalValue

	_validate_input(externalValue)
	items = externalValue.get(ITEMS)
	for item in items or ():
		preflight_overview_group(item)
	return externalValue

def preflight_input(externalValue):
	if not isinstance(externalValue, Mapping):
		return externalValue

	mimeType = externalValue.get(MIMETYPE) or externalValue.get('mimeType')
	if mimeType in ALL_MEDIA_ROLL_MIME_TYPES:
		return preflight_mediaroll(externalValue)
	elif mimeType in COURSE_OVERVIEW_GROUP_MIMETYES:
		return preflight_overview_group(externalValue)
	elif mimeType in LESSON_OVERVIEW_MIMETYES:
		return preflight_lesson_overview(externalValue)
	_validate_input(externalValue)
	return externalValue

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name=VIEW_ASSETS,
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
		externalValue = preflight_input(externalValue)
		result = copy.deepcopy(externalValue)  # return original input
		# create and validate
		contentObject = create_from_external(externalValue, notify=False)
		contentObject = self.checkContentObject(contentObject, externalValue)
		# set creator
		self._set_creator(contentObject, creator)
		# update with external
		self.updateContentObject(contentObject, externalValue, set_id=True, notify=False)
		return contentObject, result

	def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
		contentObject, externalValue = self.parseInput(creator, search_owner, externalValue)
		sources = get_all_sources(self.request)
		return contentObject, externalValue, sources

	def _do_call(self):
		creator = self.remoteUser
		contentObject, externalValue, sources = self.readCreateUpdateContentObject(creator)
		contentObject.creator = creator.username  # use string
		provided = iface_of_asset(contentObject)

		# check item does not exists and notify
		self._check_exists(provided, contentObject, creator)
		_notify_created(contentObject, self.remoteUser.username, externalValue)

		# add to connection and register
		intid_register(contentObject, registry=self._registry)
		registerUtility(self._registry,
						component=contentObject,
						provided=provided,
						name=contentObject.ntiid)

		# handle multi-part data
		if sources:
			validate_sources(self.remoteUser, contentObject, sources)
			_handle_multipart(self._course, self.remoteUser, contentObject, sources)

		self.request.response.status_int = 201
		self._handle_asset(provided, contentObject, creator.username)
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
		preflight_input(externalValue)

	def postflight(self, updatedObject, externalValue, preflight=None):
		return None

	def updateContentObject(self, contentObject, externalValue, set_id=False, notify=True):
		data = self.preflight(contentObject, externalValue)

		originalSource = copy.copy(externalValue)
		pre_hook = get_external_pre_hook(externalValue)
		result = UGDPutView.updateContentObject(self,
												contentObject,
												externalValue,
												set_id=set_id,
												notify=False,
												pre_hook=pre_hook)
		sources = get_all_sources(self.request)
		if sources:
			courses = get_presentation_asset_courses(self.context)
			if courses:  # pick first to store assets
				validate_sources(self.remoteUser, result, sources)
				_handle_multipart(courses.__iter__().next(),
								  self.remoteUser,
								  self.context,
								  sources)

		self.postflight(contentObject, externalValue, data)
		notify_modified(contentObject, originalSource)
		return result

	def __call__(self):
		result = UGDPutView.__call__(self)
		self._handle_asset(iface_of_asset(result), result, result.creator)
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
		if result is not None: # direct check in case course w/ no pkg
			return result
		package = find_interface(self.context, IContentPackage, strict=False)
		if package is not None:
			sites = get_component_hierarchy_names() # check sites
			courses = get_courses_for_packages(sites, package.ntiid)
			result = courses[0] if courses else None # should always find one
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
		preflight_lesson_overview(externalValue)
		data = {x.ntiid:x for x in contentObject}  # save groups
		return data

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
		preflight_overview_group(externalValue)
		data = {x.ntiid:x for x in contentObject}
		return data

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
		preflight_mediaroll(externalValue)
		data = {x.ntiid:x for x in contentObject}
		return data

	def postflight(self, updatedObject, externalValue, preflight):
		updated = {x.ntiid for x in updatedObject}
		for ntiid, item in preflight.items():
			if ntiid not in updated:  # ref removed
				remove_presentation_asset(item, self._registry, self._catalog)

# delete views

@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='DELETE',
			   permission=nauth.ACT_CONTENT_EDIT)
class PresentationAssetDeleteView(PresentationAssetMixin, UGDDeleteView):

	@Lazy
	def _site_name(self):
		result = component_site(self.context, 
								iface_of_asset(self.context),
								self.context.ntiid)
		return result

	@Lazy
	def _registry(self):
		return registry_by_name(self._site_name)

	def _do_delete_object(self, theObject):
		remove_presentation_asset(theObject, self._registry, self._catalog)
		return theObject

@view_config(context=INTILessonOverview)
@view_config(context=INTICourseOverviewGroup)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name=VIEW_CONTENTS,
			   request_method='DELETE',
			   permission=nauth.ACT_CONTENT_EDIT)
class AssetDeleteChildView(AbstractAuthenticatedView, NTIIDPathMixin):
	"""
	A view to delete a child underneath the given context.

	index
		This param will be used to indicate which object should be
		deleted. If the object described by `ntiid` is no longer at
		this index, the object will still be deleted, as long as it
		is unambiguous.

	:raises HTTPConflict if state has changed out from underneath user
	"""

	def _get_item(self, ntiid, index):
		"""
		Find the item/ref for the given ntiid.
		"""
		found = []
		for idx, child in enumerate(self.context):
			if 		ntiid == getattr(child, 'target', '') \
				or 	ntiid == getattr(child, 'ntiid', ''):
				if idx == index:
					# We have an exact ref hit.
					return child
				else:
					found.append(child)

		if len(found) == 1:
			# Inconsistent match, but it's unambiguous.
			return found[0]

		if found:
			# Multiple matches, none at index
			raise hexc.HTTPConflict(_('Ambiguous item ref no longer exists at this index.'))

	def __call__(self):
		values = CaseInsensitiveDict(self.request.params)
		index = values.get('index')
		ntiid = self._get_ntiid()
		item = self._get_item(ntiid, index)

		# We remove the item from our context, and clean it
		# up. We want to make sure we clean up the underlying asset.
		if item is not None:  # tests
			self.context.remove(item)  # safe op if gone already
			remove_presentation_asset(item)
			self.context.child_order_locked = True
		return hexc.HTTPOk()

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
			externalValue[MIMETYPE] = COURSE_OVERVIEW_GROUP_MIMETYES[0]
		externalValue = preflight_input(externalValue)
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
		_notify_created(contentObject, self.remoteUser.username, externalValue)

		# add to connection and register
		intid_register(contentObject, registry=self._registry)
		registerUtility(self._registry,
						provided=provided,
						component=contentObject,
						name=contentObject.ntiid)

		self.context.insert(index, contentObject)
		self._handle_overview_group(contentObject,
									creator=creator,
									extended=(self.context.ntiid,))

		notify_modified(self.context, externalValue, external_keys=(ITEMS,))
		self.context.child_order_locked = True
		self.request.response.status_int = 201
		return contentObject

@view_config(context=INTICourseOverviewGroup)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name=VIEW_CONTENTS,
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseOverviewGroupOrderedContentsView(PresentationAssetSubmitViewMixin,
											 ModeledContentUploadRequestUtilsMixin,
											 IndexedRequestMixin):  # order matters
	"""
	We accept asset items by index here. We handle two types specially here:

	1. We turn media objects into media refs here, given an NTIID.
	2. We turn timeline ntiids into timeline objects to place directly
	in the overview group (since these objects do not have refs).
	"""

	content_predicate = IGroupOverViewable.providedBy

	def _remove_ntiids(self, ext_obj, do_remove):
		# Do not remove our media ntiids, these will be our ref targets.
		# If we don't have a mimeType, we need the ntiid to fetch the (video) object.
		mimeType = ext_obj.get(MIMETYPE) or ext_obj.get('mimeType')
		is_media = bool(mimeType in VIDEO_MIMETYES or mimeType in AUDIO_MIMETYES)
		if mimeType and not is_media and mimeType not in TIMELINE_MIMETYES:
			super(CourseOverviewGroupOrderedContentsView, self)._remove_ntiids(ext_obj, do_remove)

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

			if INTITimeline.providedBy( resolved ):
				# Short circuit; we need to use this.
				return resolved
			elif 	INTIMedia.providedBy(resolved) \
				or 	INTIMediaRef.providedBy(resolved):
				externalValue[MIMETYPE] = resolved.mimeType
			else:
				# We did not have a mimetype, and we have an ntiid the resolved
				# into an unexpected type; blow chunks.
				raise hexc.HTTPUnprocessableEntity(_('Invalid overview group item'))

		mimeType = externalValue.get(MIMETYPE) or externalValue.get('mimeType')
		if mimeType in VIDEO_MIMETYES or mimeType in AUDIO_MIMETYES:
			if isinstance(externalValue, Mapping):
				internalization_ntiaudioref_pre_hook(None, externalValue)
				internalization_ntivideoref_pre_hook(None, externalValue)
		return preflight_input(externalValue)

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
		if isinstance( externalValue, Mapping ):
			contentObject = create_from_external(externalValue, notify=False)
			contentObject = self.checkContentObject(contentObject, externalValue)
			self._set_creator(contentObject, creator)
		else:
			contentObject = externalValue
		return contentObject, external_input

	def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
		contentObject, externalValue = self.parseInput(creator, search_owner, externalValue)
		sources = get_all_sources(self.request)
		if sources:  # multi-part data
			validate_sources(self.remoteUser, contentObject, sources)
			_handle_multipart(self._course, self.remoteUser, contentObject, sources)
		return contentObject, externalValue

	def _do_call(self):
		index = self._get_index()
		creator = self.remoteUser
		contentObject, externalValue = self.readCreateUpdateContentObject(creator)
		provided = iface_of_asset(contentObject)

		__traceback_info__ = contentObject

		# check item does not exists and notify
		self._check_exists(provided, contentObject, creator)
		_notify_created(contentObject, self.remoteUser.username, externalValue)

		# add to connection and register
		intid_register(contentObject, registry=self._registry)
		registerUtility(self._registry,
						provided=provided,
						component=contentObject,
						name=contentObject.ntiid)

		parent = self.context.__parent__
		extended = (self.context.ntiid,) + ((parent.ntiid,) if parent is not None else ())
		self.context.insert(index, contentObject)
		self._handle_asset(provided,
						   contentObject,
						   creator=creator,
						   extended=extended)

		notify_modified(self.context, externalValue, external_keys=(ITEMS,))
		self.request.response.status_int = 201
		self.context.child_order_locked = True

		# We don't return media refs in the overview group.
		# So don't here either.
		if INTIMediaRef.providedBy(contentObject):
			contentObject = INTIMedia(contentObject)
		return self.transformOutput(contentObject)

@view_config(name=VIEW_RECURSIVE_AUDIT_LOG)
@view_config(name=VIEW_RECURSIVE_TX_HISTORY)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_CONTENT_EDIT,
			   context=INTILessonOverview)
class RecursiveCourseTransactionHistoryView( AbstractRecursiveTransactionHistoryView ):
	"""
	A batched view to get all edits that have occurred in the lesson, recursively.
	"""

	def _get_items(self):
		result = []
		self._accum_lesson_transactions( self.context, result )
		return result
