#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory as _

import six
import copy
import uuid
from itertools import chain
from urlparse import urlparse
from collections import Mapping

import transaction

from zope import interface

from zope.event import notify

from zope.security.interfaces import NoInteraction
from zope.security.management import getInteraction

from pyramid.view import view_config

from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.renderers.interfaces import INoHrefInResponse

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile import validate_sources

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDDeleteView
from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.common.maps import CaseInsensitiveDict

from nti.common.property import Lazy

from nti.coremetadata.interfaces import IPublishable

from nti.contentfolder.interfaces import IContentFolder

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation import AUDIO_MIMETYES
from nti.contenttypes.presentation import VIDEO_MIMETYES
from nti.contenttypes.presentation import LESSON_OVERVIEW_MIMETYES
from nti.contenttypes.presentation import ALL_MEDIA_ROLL_MIME_TYPES
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import COURSE_OVERVIEW_GROUP_MIMETYES

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIAudioRoll
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import INTIVideoRoll
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import PresentationAssetCreatedEvent

from nti.contenttypes.presentation.internalization import internalization_ntiaudioref_pre_hook
from nti.contenttypes.presentation.internalization import internalization_ntivideoref_pre_hook

from nti.contenttypes.presentation.utils import create_from_external
from nti.contenttypes.presentation.utils import get_external_pre_hook

from nti.dataserver import authorization as nauth

from nti.externalization.oids import to_external_ntiid_oid
from nti.externalization.internalization import notify_modified
from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import LocatedExternalDict
from nti.externalization.externalization import StandardExternalFields

from nti.namedfile.file import name_finder
from nti.namedfile.file import safe_filename

from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.utils import registerUtility
from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

from ..utils import intid_register
from ..utils import add_2_connection
from ..utils import make_asset_ntiid
from ..utils import registry_by_name
from ..utils import component_registry
from ..utils import get_course_packages
from ..utils import remove_presentation_asset
from ..utils import get_presentation_asset_courses

from .view_mixins import slugify
from .view_mixins import hexdigest
from .view_mixins import get_namedfile
from .view_mixins import get_render_link
from .view_mixins import get_assets_folder
from .view_mixins import get_file_from_link
from .view_mixins import IndexedRequestMixin
from .view_mixins import AbstractChildMoveView
from .view_mixins import PublishVisibilityMixin

from . import VIEW_ASSETS
from . import VIEW_CONTENTS
from . import VIEW_NODE_MOVE

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE

# helper functions

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
	registry = get_registry(registry)
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

def _get_unique_filename(folder, context, name):
	name = getattr(context, 'filename', None) or getattr(context, 'name', None) or name
	name = safe_filename(name_finder(name))
	result = slugify(name, folder)
	return result

def _remove_file(href):
	named = get_file_from_link(href) if href and isinstance(href, six.string_types) else None
	container = getattr(named, '__parent__', None)
	if IContentFolder.providedBy(container):
		return container.remove(named)
	return False

def _handle_multipart(context, contentObject, sources, provided=None):
	provided = iface_of_asset(contentObject) if provided is None else provided
	assets = get_assets_folder(context)
	for name, source in sources.items():
		if name in provided:
			# remove existing
			_remove_file(getattr(contentObject, name, None))
			# save a new file
			file_key = _get_unique_filename(assets, source, name)
			namedfile = get_namedfile(source, file_key)
			assets[file_key] = namedfile  # add to container
			location = get_render_link(namedfile)
			setattr(contentObject, name, location)

# GET views

@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
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
			   request_method='GET')
class NoHrefAssetGetView(PresentationAssetGetView):

	def __call__(self):
		result = PresentationAssetGetView.__call__(self)
		result = to_external_object(result)
		interface.alsoProvides(result, INoHrefInResponse)
		return result

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name=VIEW_ASSETS,
			   request_method='GET',
			   permission=nauth.ACT_CONTENT_EDIT)
class GetCoursePresentationAssetPostView(AbstractAuthenticatedView):

	def __call__(self):
		total = 0
		result = LocatedExternalDict()
		result[ITEMS] = items = {}
		course = ICourseInstance(self.context)
		for container in chain((course, get_course_packages(course))):
			container = IPresentationAssetContainer(container, None) or {}
			for item in container.values():
				items[item.ntiid] = item
			total += len(container)
		result['ItemCount'] = result['Total'] = total
		return result

# POST/PUT views

@view_config(route_name='objects.generic.traversal',
			 request_method='POST',
			 context=INTILessonOverview,
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name=VIEW_NODE_MOVE)
class LessonOverviewMoveView(AbstractChildMoveView):
	"""
	Move the given object between lessons or overview groups.
	"""

	# TODO
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

class PresentationAssetMixin(object):

	@Lazy
	def _catalog(self):
		return get_library_catalog()

	@Lazy
	def _extra(self):
		return str(uuid.uuid4()).split('-')[0]

	@Lazy
	def _registry(self):
		return get_registry()

class PresentationAssetSubmitViewMixin(PresentationAssetMixin,
									   AbstractAuthenticatedView):

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
		# for return None for auto-generate NTIIDs,
		if 		ntiid \
			and	(INTICourseOverviewGroup.providedBy(item) or IAssetRef.providedBy(item)) \
			and TYPE_UUID in get_specific(ntiid):
			ntiid = None
		return ntiid

	def _check_exists(self, provided, item, creator):
		ntiid = self._get_ntiid(item)
		if ntiid:
			if self._registry.queryUtility(provided, name=ntiid):
				raise hexc.HTTPUnprocessableEntity(_("Asset already exists."))
		else:
			item.ntiid = make_asset_ntiid(provided, creator, extra=self._extra)
		return item

	def _set_creator(self, item, creator):
		creator = getattr(creator, 'username', creator)
		if not getattr(item, 'creator', None):
			item.creator = creator

	def _handle_package_asset(self, provided, item, creator, extended=None):
		self._set_creator(item, creator)

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
									namespace=namespace)

		# index item
		item_extended = list(extended or ()) + containers
		self._catalog.index(item, container_ntiids=item_extended, namespace=namespace)

	def _handle_related_work(self, provided, item, creator, extended=None):
		self._set_creator(item, creator)
		self._handle_package_asset(provided, item, creator, extended)

		# capture updated/previous data
		ntiid, href = item.target, item.href
		contentType = item.type or u'application/octet-stream'  # default

		# if client has uploaded a file, capture contentType and target ntiid
		if self.request.POST and 'href' in self.request.POST:
			named = get_file_from_link(href) if href else None
			contentType = unicode(named.contentType or u'') if named else contentType
			ntiid = to_external_ntiid_oid(named) if named is not None else ntiid

		# parse href
		parsed = urlparse(href) if href else None
		if parsed is not None and (parsed.scheme or parsed.netloc):  # full url
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
			self._catalog.index(x, container_ntiids=item_extended)

		# index item
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(item, container_ntiids=item_extended)

	def _handle_group_over_viewable(self, provided, item, creator, extended=None):
		# set creator
		self._set_creator(item, creator)

		# add to course container
		containers = _add_2_container(self._course, item, packages=False)
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(item, container_ntiids=item_extended)

		# find a content unit
		content_unit = None
		if INTIAssignmentRef.providedBy(item) and not item.title:
			assignment = self._registry.queryUtility(IQAssignment, name=item.target or '')
			item.title = assignment.title if assignment is not None else item.title
			content_unit = assignment.__parent__ if assignment is not None else None
		elif INTIQuestionSetRef.providedBy(item):
			qset = self._registry.queryUtility(IQuestionSet, name=item.target or '')
			item.question_count = len(qset) if qset is not None else item.question_count
			content_unit = qset.__parent__ if qset is not None else None
		elif INTISurveyRef.providedBy(item):
			survey = self._registry.queryUtility(IQSurvey, name=item.target or '')
			item.question_count = len(survey) if survey is not None else item.question_count
			content_unit = survey.__parent__ if survey is not None else None

		# set container id
		if content_unit is not None:
			item.containerId = content_unit.ntiid

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
							namespace=namespace)

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
							namespace=namespace)

	def _handle_other_asset(self, provided, item, creator, extended=None):
		containers = _add_2_container(self._course, item, packages=False)
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(item, container_ntiids=item_extended)

	def _handle_asset(self, provided, item, creator, extended=()):
		if provided in PACKAGE_CONTAINER_INTERFACES:
			if INTIRelatedWorkRef.providedBy(item):
				self._handle_related_work(provided, item, creator, extended)
			else:
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

# preflight routines

def preflight_mediaroll(externalValue):
	if not isinstance(externalValue, Mapping):
		return externalValue

	items = externalValue.get(ITEMS)

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
	def _registry(self):
		folder = find_interface(self._course, IHostPolicyFolder, strict=False)
		result = registry_by_name(folder.__name__)
		return result

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
		if sources:  # multi-part data
			validate_sources(contentObject, sources)
			_handle_multipart(self._course, contentObject, sources)
		return contentObject, externalValue

	def _do_call(self):
		creator = self.remoteUser
		contentObject, externalValue = self.readCreateUpdateContentObject(creator)
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

		self.request.response.status_int = 201
		self._handle_asset(provided, contentObject, creator.username)
		return contentObject

# put views

@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='PUT',
			   permission=nauth.ACT_CONTENT_EDIT)
class PresentationAssetPutView(PresentationAssetSubmitViewMixin,
							   UGDPutView):  # order matters

	@Lazy
	def _registry(self):
		provided = iface_of_asset(self.context)
		return component_registry(self.context,
								  provided=provided,
								  name=self.context.ntiid)

	def preflight(self, contentObject, externalValue):
		preflight_input(externalValue)

	def postflight(self, updatedObject, externalValue, preflight=None):
		return None

	def updateContentObject(self, contentObject, externalValue, set_id=False, notify=True):
		data = self.preflight(contentObject, externalValue)

		pre_hook = get_external_pre_hook(externalValue)
		result = UGDPutView.updateContentObject(self,
												contentObject,
												externalValue,
												set_id=set_id,
												notify=notify,
												pre_hook=pre_hook)
		sources = get_all_sources(self.request)
		if sources:
			courses = get_presentation_asset_courses(self.context)
			if courses:  # pick first to store assets
				validate_sources(result, sources)
				_handle_multipart(courses.__iter__().next(), self.context, sources)

		self.postflight(contentObject, externalValue, data)
		return result

	def __call__(self):
		result = UGDPutView.__call__(self)
		self._handle_asset(iface_of_asset(result), result, result.creator)
		return result

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
	def _registry(self):
		provided = iface_of_asset(self.context)
		return component_registry(self.context,
								  provided=provided,
								  name=self.context.ntiid)

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
class AssetDeleteChildView(AbstractAuthenticatedView,
						   ModeledContentUploadRequestUtilsMixin):

	def __call__(self):
		values = CaseInsensitiveDict(self.readInput())
		ntiid = values.get('ntiid')
		item = find_object_with_ntiid(ntiid)
		if item is None:
			raise hexc.HTTPConflict(_('Item no longer exists'))

		# For media objects, we want to remove the actual
		# ref, but clients will only send target ntiids.
		if INTIMedia.providedBy(item):
			for child in self.context:
				if getattr(child, 'target', '') == ntiid:
					item = child
					break

		# We remove the item from our context, and clean it
		# up. But we want to make sure we don't clean up the
		# underlying asset items in a group.
		self.context.remove(item)
		if INTICourseOverviewGroup.providedBy(item):
			remove_presentation_asset(item)
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

	content_predicate = IGroupOverViewable.providedBy

	def _remove_ntiids(self, ext_obj, do_remove):
		# Do not remove our media ntiids, these will be our ref targets.
		# If we don't have a mimeType, we need the ntiid to fetch the (video) object.
		mimeType = ext_obj.get(MIMETYPE) or ext_obj.get('mimeType')
		is_media = bool(mimeType in VIDEO_MIMETYES or mimeType in AUDIO_MIMETYES)
		if mimeType and not is_media:
			super(CourseOverviewGroupOrderedContentsView, self)._remove_ntiids(ext_obj, do_remove)

	def preflight_video(self, externalValue):
		"""
		Swizzle media into refs for overview groups. If we're missing a mimetype, the given
		ntiid *must* resolve to a video. All other types should be fully defined (ref) objects.
		"""
		if isinstance(externalValue, Mapping) and MIMETYPE not in externalValue:
			ntiid = externalValue.get('ntiid') or externalValue.get(NTIID)
			__traceback_info__ = ntiid
			if not ntiid:
				raise hexc.HTTPUnprocessableEntity(_('Missing overview group item NTIID'))
			resolved = find_object_with_ntiid(ntiid)
			if resolved is None:
				raise hexc.HTTPUnprocessableEntity(_('Missing overview group item'))
			if (INTIMedia.providedBy(resolved) or INTIMediaRef.providedBy(resolved)):
				externalValue[MIMETYPE] = resolved.mimeType
			else:
				# We did not have a mimetype, and we have an ntiid the resolved
				# into an unexpected type; blow chunks.
				raise hexc.HTTPUnprocessableEntity(_('Invalid overview group item'))

		mimeType = externalValue.get(MIMETYPE) or externalValue.get('mimeType')
		if mimeType in VIDEO_MIMETYES or mimeType in AUDIO_MIMETYES:
			if not isinstance(externalValue, Mapping):
				return externalValue

			internalization_ntiaudioref_pre_hook(None, externalValue)
			internalization_ntivideoref_pre_hook(None, externalValue)
		return externalValue

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
		externalValue = self.preflight_video(externalValue)
		externalValue = preflight_input(externalValue)
		result = copy.deepcopy(externalValue)  # return original input
		# create object
		contentObject = create_from_external(externalValue, notify=False)
		contentObject = self.checkContentObject(contentObject, externalValue)
		# set creator
		self._set_creator(contentObject, creator)
		return contentObject, result

	def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
		contentObject, externalValue = self.parseInput(creator, search_owner, externalValue)
		sources = get_all_sources(self.request)
		if sources:  # multi-part data
			validate_sources(contentObject, sources)
			_handle_multipart(self._course, contentObject, sources)
		return contentObject, externalValue

	def _do_call(self):
		index = self._get_index()
		creator = self.remoteUser
		contentObject, externalValue = self.readCreateUpdateContentObject(creator)
		provided = iface_of_asset(contentObject)

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

		# We don't return media refs in the overview group.
		# So don't here either.
		if INTIMediaRef.providedBy(contentObject):
			contentObject = INTIMedia(contentObject)
		return contentObject
