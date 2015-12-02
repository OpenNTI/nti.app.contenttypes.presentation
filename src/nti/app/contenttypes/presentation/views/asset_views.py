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
import time
import uuid
from itertools import chain
from urlparse import urlparse

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

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDDeleteView
from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.common.property import Lazy
from nti.common.time import time_to_64bit_int

from nti.coremetadata.interfaces import IPublishable

from nti.contentfolder.interfaces import IContentFolder

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import COURSE_OVERVIEW_GROUP_MIMETYES

from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import PresentationAssetCreatedEvent

from nti.contenttypes.presentation.utils import create_from_external
from nti.contenttypes.presentation.utils import get_external_pre_hook

from nti.dataserver import authorization as nauth

from nti.externalization.oids import to_external_ntiid_oid
from nti.externalization.internalization import notify_modified
from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import StandardExternalFields

from nti.namedfile.file import name_finder
from nti.namedfile.file import safe_filename

from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.site.utils import registerUtility

from ..utils import get_course_packages
from ..utils import get_presentation_asset_courses

from .view_mixins import slugify
from .view_mixins import hexdigest
from .view_mixins import remove_asset
from .view_mixins import get_namedfile
from .view_mixins import intid_register
from .view_mixins import get_render_link
from .view_mixins import add_2_connection
from .view_mixins import get_assets_folder
from .view_mixins import component_registry
from .view_mixins import get_file_from_link
from .view_mixins import AbstractChildMoveView
from .view_mixins import PublishVisibilityMixin

from . import VIEW_NODE_MOVE

ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE

# helper functions

def _make_asset_ntiid(nttype, creator, base=None, extra=None):
	if not isinstance(nttype, six.string_types):
		nttype = nttype.__name__[1:]

	current_time = time_to_64bit_int(time.time())
	creator = getattr(creator, 'username', creator)
	provider = get_provider(base) or 'NTI' if base else 'NTI'

	specific_base = get_specific(base) if base else None
	if specific_base:
		specific_base += '.%s.%s' % (creator, current_time)
	else:
		specific_base = '%s.%s' % (creator, current_time)

	if extra:
		specific_base = specific_base + ".%s" % extra
	specific = make_specific_safe(specific_base)

	ntiid = make_ntiid(nttype=nttype,
					   base=base,
					   provider=provider,
					   specific=specific)
	return ntiid

def principalId():
	try:
		return getInteraction().participations[0].principal.id
	except (NoInteraction, IndexError, AttributeError):
		return None

def _notify_created(item, principal=None, externalValue=None):
	add_2_connection(item) # required
	principal = principal or principalId() # always get a principal
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

def _add_2_container(context, item, pacakges=False):
	result = []
	_add_2_courses(context, item)
	if pacakges:
		result.extend(_add_2_packages(context, item))
	entry = ICourseCatalogEntry(context, None)
	if entry is not None:
		result.append(entry.ntiid)
	return result

def _canonicalize(items, creator, base=None, registry=None):
	result = []
	registry = get_registry(registry)
	for idx, item in enumerate(items):
		created = True
		provided = iface_of_asset(item)
		if not item.ntiid:
			item.ntiid = _make_asset_ntiid(provided, creator, base=base, extra=idx)
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
			filename = _get_unique_filename(assets, source, name)
			namedfile = get_namedfile(source, filename)
			assets[filename] = namedfile  # add to container
			location = get_render_link(namedfile)
			setattr(contentObject, name, location)

# GET views

# TODO: Don't we need to validate READ access?
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

# POST/PUT views

@view_config(context=INTILessonOverview)
@view_config(context=INTICourseOverviewGroup)
@view_defaults(route_name='objects.generic.traversal',
			 request_method='POST',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name=VIEW_NODE_MOVE)
class ObjectMoveView( AbstractChildMoveView ):
	"""
	Move the given object between lessons or overview groups.
	"""

	# TODO
	notify_type = None

	def _get_context_ntiid(self):
		return self.context.ntiid

	def _remove_from_parent( self, parent, obj ):
		parent.remove( obj )

	def _add_to_parent( self, parent, obj, index ):
		# TODO: Probably need to add an object level API.
		# Remove from our list if it exists, and then insert at.
		parent.remove(obj)
		parent.items.insert( index, obj )

	def _get_children_ntiids(self, parent_ntiid):
		result = set()
		result.add( parent_ntiid )
		def _recur(node):
			val = getattr(node, 'ntiid', None)
			if val:
				result.add(val)
			for child in node.items():
				_recur(child)

		_recur( self.context )
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
		if 		INTICourseOverviewGroup.providedBy(item) \
			and TYPE_UUID in get_specific(ntiid):
			ntiid = None
		return ntiid

	def _check_exists(self, provided, item, creator):
		ntiid = self._get_ntiid(item)
		if ntiid:
			if self._registry.queryUtility(provided, name=ntiid):
				raise hexc.HTTPUnprocessableEntity(_("Asset already exists."))
		else:
			item.ntiid = _make_asset_ntiid(provided, creator, extra=self._extra)
		return item

	def _handle_package_asset(self, provided, item, creator, extended=None):
		containers = _add_2_container(self._course, item, pacakges=True)
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
				_add_2_container(self._course, x, pacakges=True)
				self._catalog.index(x, container_ntiids=item_extended,
									namespace=namespace)

		# index item
		item_extended = list(extended or ()) + containers
		self._catalog.index(item, container_ntiids=item_extended, namespace=namespace)

	def _handle_related_work(self, provided, item, creator, extended=None):
		self._handle_package_asset(provided, item, creator, extended)
		if not item.target:
			href = item.href
			parsed = urlparse(href) if href else None
			if href and parsed.scheme or parsed.netloc:  # full url
				ntiid = make_ntiid(nttype=TYPE_UUID,
								   provider='NTI',
								   specific=hexdigest(item.href))
			else:
				named = get_file_from_link(href) if href else None
				ntiid = to_external_ntiid_oid(named) if named is not None else None
			item.target = ntiid

	def _handle_media_roll(self, provided, item, creator, extended=None):
		containers = _add_2_container(self._course, item, pacakges=False)

		# register unique copies
		_canonicalize(item.Items, creator, base=item.ntiid, registry=self._registry)

		# add media roll ntiid
		item_extended = tuple(extended or ()) + tuple(containers or ()) + (item.ntiid,)
		item_extended = set(item_extended)
		for x in item.Items:
			_add_2_container(self._course, x, pacakges=False)
			self._catalog.index(x, container_ntiids=item_extended)

		# index item
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(item, container_ntiids=item_extended)

	def _handle_overview_group(self, group, creator, extended=None):
		# add to course container
		containers = _add_2_container(self._course, group, pacakges=False)

		# have unique copies of group items
		_canonicalize(group.Items, creator, registry=self._registry, base=group.ntiid)

		# include group ntiid in containers
		item_extended = list(extended or ()) + containers + [group.ntiid]
		item_extended = set(item_extended)
		# process group items
		for x in group.Items:
			if INTIMediaRoll.providedBy(x):
				provided = iface_of_asset(x)
				self._handle_media_roll(provided, x, creator, item_extended)
			else:
				_add_2_container(self._course, x, pacakges=False)
				self._catalog.index(x, container_ntiids=item_extended)

		# index group
		lesson = group.__parent__
		namespace = to_external_ntiid_oid(lesson) if lesson is not None else None
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(group, container_ntiids=item_extended,
							namespace=namespace)

	def _handle_lesson_overview(self, lesson, creator, extended=None):
		# add to course container
		containers = _add_2_container(self._course, lesson, pacakges=False)

		# have unique copies of lesson groups
		_canonicalize(lesson.Items, creator, registry=self._registry, base=lesson.ntiid)

		# extend but don't add containers
		item_extended = list(extended or ()) + [lesson.ntiid]

		# process lesson groups
		for group in lesson.Items:
			if group.__parent__ is not None and group.__parent__ != lesson:
				msg = _("Overview group has been used by another lesson")
				raise hexc.HTTPUnprocessableEntity(msg)

			# take ownership
			group.__parent__ = lesson
			self._check_exists(INTICourseOverviewGroup, group, creator)
			self._handle_overview_group(group,
										creator=creator,
										extended=item_extended)

		# index lesson item
		namespace = to_external_ntiid_oid(lesson)
		item_extended = tuple(extended or ()) + tuple(containers or ())
		self._catalog.index(lesson, container_ntiids=item_extended,
							namespace=namespace)

	def _handle_other_asset(self, item, creator, extended=None):
		containers = _add_2_container(self._course, item, pacakges=False)
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
		elif provided == INTICourseOverviewGroup:
			self._handle_overview_group(item, creator, extended)
		elif provided == INTILessonOverview:
			self._handle_lesson_overview(item, creator, extended)
		else:
			self._handle_other_asset(item, creator, extended)
		return item

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name="assets",
			   request_method='POST',
			   permission=nauth.ACT_CONTENT_EDIT)
class PresentationAssetPostView(PresentationAssetSubmitViewMixin,
								ModeledContentUploadRequestUtilsMixin):

	content_predicate = IPresentationAsset.providedBy

	def checkContentObject(self, contentObject, externalValue):
		if contentObject is None or not self.content_predicate(contentObject):
			transaction.doom()
			logger.debug("Failing to POST: input of unsupported/missing Class: %s => %s",
						 externalValue, contentObject)
			raise hexc.HTTPUnprocessableEntity(_('Unsupported/missing Class'))
		return contentObject

	def parseInput(self, creator, search_owner=False, externalValue=None):
		externalValue = self.readInput() if not externalValue else externalValue
		contentObject = create_from_external(externalValue, notify=False)
		contentObject = self.checkContentObject(contentObject, externalValue)
		contentObject.creator = getattr(creator, 'username', creator)  # use string
		self.updateContentObject(contentObject, externalValue, set_id=True, notify=False)
		return contentObject, externalValue

	def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
		contentObject, externalValue = self.parseInput(creator, search_owner, externalValue)
		sources = get_all_sources(self.request)
		if sources:  # multi-part data
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

@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='PUT',
			   permission=nauth.ACT_CONTENT_EDIT)
class PresentationAssetPutView(PresentationAssetSubmitViewMixin, UGDPutView):

	@Lazy
	def _registry(self):
		provided = iface_of_asset(self.context)
		return component_registry(self.context,
								  provided=provided,
								  name=self.context.ntiid)

	def readInput(self, value=None):
		result = UGDPutView.readInput(self, value=value)
		result.pop('ntiid', None)
		result.pop('NTIID', None)
		return result

	def updateContentObject(self, contentObject, externalValue, set_id=False, notify=True):
		provided = iface_of_asset(contentObject)
		if provided == INTILessonOverview:
			data = {x.ntiid:x for x in contentObject.Items}  # save groups
		else:
			data = None

		# update object
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
				_handle_multipart(courses.__iter__().next(), self.context, sources)

		# unregister any old data
		if data and provided == INTILessonOverview:
			updated = {x.ntiid for x in contentObject.Items}
			for ntiid, group in data.items():
				if ntiid not in updated:  # group removed
					remove_asset(group, self._registry, self._catalog)

		return result

	def __call__(self):
		result = UGDPutView.__call__(self)
		self._handle_asset(iface_of_asset(result), result, result.creator)
		return result

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
		remove_asset(theObject, self._registry, self._catalog)
		return theObject

@view_config(context=INTILessonOverview)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name="contents",
			   permission=nauth.ACT_CONTENT_EDIT)
class LessonOverviewOrderedContentsView(PresentationAssetSubmitViewMixin,
										ModeledContentUploadRequestUtilsMixin):

	content_predicate = INTICourseOverviewGroup.providedBy

	def checkContentObject(self, contentObject, externalValue):
		if contentObject is None or not self.content_predicate(contentObject):
			transaction.doom()
			logger.debug("Failing to POST: input of unsupported/missing Class: %s => %s",
						 externalValue, contentObject)
			raise hexc.HTTPUnprocessableEntity(_('Unsupported/missing Class'))
		return contentObject

	def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
		externalValue = self.readInput() if not externalValue else externalValue
		# check for mimeType
		if MIMETYPE not in externalValue:
			externalValue[MIMETYPE] = COURSE_OVERVIEW_GROUP_MIMETYES[0]
		# create object
		contentObject = create_from_external(externalValue, notify=False)
		contentObject = self.checkContentObject(contentObject, externalValue)
		contentObject.creator = getattr(creator, 'username', creator)  # use string
		return contentObject, externalValue

	def _do_call(self):
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

		self.context.append(contentObject)
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
			   name="contents",
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseOverviewGroupOrderedContentsView(PresentationAssetSubmitViewMixin,
											 ModeledContentUploadRequestUtilsMixin):

	content_predicate = IGroupOverViewable.providedBy

	def checkContentObject(self, contentObject, externalValue):
		if contentObject is None or not self.content_predicate(contentObject):
			transaction.doom()
			logger.debug("Failing to POST: input of unsupported/missing Class: %s => %s",
						 externalValue, contentObject)
			raise hexc.HTTPUnprocessableEntity(_('Unsupported/missing Class'))
		return contentObject

	def parseInput(self, creator, search_owner=False, externalValue=None):
		externalValue = self.readInput() if not externalValue else externalValue
		contentObject = create_from_external(externalValue, notify=False)
		contentObject = self.checkContentObject(contentObject, externalValue)
		contentObject.creator = getattr(creator, 'username', creator)  # use string
		return contentObject, externalValue

	def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
		contentObject, externalValue = self.parseInput(creator, search_owner, externalValue)
		sources = get_all_sources(self.request)
		if sources: # multi-part data
			_handle_multipart(self._course, contentObject, sources)
		return contentObject, externalValue

	def _do_call(self):
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
		self.context.append(contentObject)
		self._handle_asset(provided,
						   contentObject,
						   creator=creator,
						   extended=extended)

		notify_modified(self.context, externalValue, external_keys=(ITEMS,))
		self.request.response.status_int = 201
		return contentObject
