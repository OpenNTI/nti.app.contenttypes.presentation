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

from zope import interface
from zope import lifecycleevent

from ZODB.interfaces import IConnection

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.renderers.interfaces import INoHrefInResponse

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.common.property import Lazy
from nti.common.time import time_to_64bit_int

from nti.coremetadata.interfaces import IRecordable
from nti.coremetadata.interfaces import IPublishable

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES

from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.utils import create_from_external

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.site.utils import registerUtility

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

def _get_course_packages(context):
	course = ICourseInstance(context)
	try:
		packs = course.ContentPackageBundle.ContentPackages
	except AttributeError:
		packs = (course.legacy_content_package,)
	return packs

def _notify_created(item):
	lifecycleevent.created(item)
	if IPublishable.providedBy(item) and item.is_published():
		item.unpublish()
	if IRecordable.providedBy(item):
		item.locked = True

def _db_connection(registry=None):
	registry = get_registry(registry)
	result = IConnection(registry, None)
	return result

def _intid_register(item, registry=None, connection=None):
	connection = _db_connection(registry) if connection is None else connection
	if connection is not None:
		connection.add(item)
		lifecycleevent.added(item)
		return True
	return False

def _add_2_packages(context, item):
	result = []
	for package in _get_course_packages(context):
		container = IPresentationAssetContainer(package)
		container[item.ntiid] = item
		result.append(package.ntiid)
	return result

def _add_2_course(context, item):
	course = ICourseInstance(context)
	container = IPresentationAssetContainer(course)
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
	entry = ICourseCatalogEntry(context)
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
			_intid_register(item, registry)
			registerUtility(registry, item, provided, name=item.ntiid)
	return result

# GET views

@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET')
class PresentationAssetGetView(GenericGetView):

	def __call__(self):
		accept = self.request.headers.get(b'Accept') or u''
		if accept == 'application/vnd.nextthought.pageinfo+json':
			raise hexc.HTTPNotAcceptable()
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

class AssetViewMixin(object):

	def readInput(self, value=None):
		result = AssetPutViewMixin.readInput(self, value=value)
		result.pop('ntiid', None)
		result.pop('NTIID', None)
		return result


class AssetPutViewMixin(object):

	def readInput(self, value=None):
		result = AssetPutViewMixin.readInput(self, value=value)
		result.pop('ntiid', None)
		result.pop('NTIID', None)
		return result

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name="assets",
			   request_method='POST')
class AssetPostView(AbstractAuthenticatedView, ModeledContentUploadRequestUtilsMixin):

	content_predicate = IPresentationAsset.providedBy

	@Lazy
	def _course(self):
		parent = self.context
		result = ICourseInstance(parent)
		return result

	@Lazy
	def _entry(self):
		result = ICourseCatalogEntry(self.context)
		return result

	@Lazy
	def _catalog(self):
		return get_library_catalog()

	@Lazy
	def _extra(self):
		return str(uuid.uuid4()).split('-')[0]

	@Lazy
	def _registry(self):
		return get_registry()

	def _get_ntiid(self, item):
		ntiid = item.ntiid
		if INTICourseOverviewGroup.providedBy(item) and TYPE_UUID in get_specific(ntiid):
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

	def _handle_package_asset(self, provided, item, creator):
		containers = _add_2_container(self._course, item, pacakges=True)
		if provided == INTISlideDeck:
			base = item.ntiid

			# register unique copies
			_canonicalize(item.Slides, creator, base=base, registry=self._registry)
			_canonicalize(item.Videos, creator, base=base, registry=self._registry)

			# register in containers and index
			for x in chain(item.Slides, item.Videos):
				_add_2_container(self._course, x, pacakges=True)
				self._catalog.index(x, container_ntiids=containers,
				  					namespace=containers[0])  # first pkg

		# index item
		self._catalog.index(item, container_ntiids=containers,
				  			namespace=containers[0])  # first pkg

	def _handle_overview_group(self, group, creator, extended=None):
		# add to course container
		containers = _add_2_container(self._course, group, pacakges=False)

		# have unique copies of group items
		_canonicalize(group.Items, creator, registry=self._registry, base=group.ntiid)

		# include group ntiid in containers
		item_extended = list(extended or ()) + containers + [group.ntiid]

		# process group items
		for x in group.Items:
			_add_2_container(self._course, x, pacakges=False)
			self._catalog.index(x, container_ntiids=item_extended)

		# index group
		item_extended = list(extended or ()) + containers
		self._catalog.index(group, container_ntiids=item_extended)

	def _handle_lesson_overview(self, lesson, creator):
		# add to course container
		containers = _add_2_container(self._course, lesson, pacakges=False)

		# have unique copies of lesson groups
		_canonicalize(lesson.Items, creator, registry=self._registry, base=lesson.ntiid)

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
										extended=(lesson.ntiid,))

		# index lesson item
		self._catalog.index(lesson, container_ntiids=containers)

	def _handle_other_asset(self, item, creator):
		containers = _add_2_container(self._course, item, pacakges=False)
		self._catalog.index(item, container_ntiids=containers)

	def _handle_asset(self, provided, item, creator):
		if provided in PACKAGE_CONTAINER_INTERFACES:
			self._handle_package_asset(provided, item, creator)
		elif provided == INTICourseOverviewGroup:
			self._handle_overview_group(item, creator)
		elif provided == INTILessonOverview:
			self._handle_lesson_overview(item, creator)
		else:
			self._handle_other_asset(item, creator)
		return item

	def readCreateUpdateContentObject(self, user, search_owner=False, externalValue=None):
		creator = user
		externalValue = self.readInput() if not externalValue else externalValue
		containedObject = create_from_external(externalValue, notify=False)
		containedObject.creator = getattr(creator, 'username', creator)  # use string
		self.updateContentObject(containedObject, externalValue, set_id=True, notify=False)
		return containedObject

	def _do_call(self):
		creator = self.remoteUser
		content_object = self.readCreateUpdateContentObject(creator)
		content_object.creator = creator.username  # use string
		provided = iface_of_asset(content_object)

		# check item does not exists and notify
		self._check_exists(provided, content_object, creator)
		_notify_created(content_object)

		# add to connection and register
		_intid_register(content_object, registry=self._registry)
		registerUtility(self._registry,
						component=content_object,
						provided=provided,
						name=content_object.ntiid)

		self.request.response.status_int = 201
		self._handle_asset(provided, content_object, creator.username)
		return content_object
