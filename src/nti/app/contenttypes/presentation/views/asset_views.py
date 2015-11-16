#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory as _

import time
import uuid
from itertools import chain

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.intid import IIntIds

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

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES

from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.site.utils import registerUtility

from . import AssetsPathAdapter

def make_asset_ntiid(nttype, creator, base=None, extra=None):
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

def get_course_packages(course):
	try:
		packs = course.ContentPackageBundle.ContentPackages
	except AttributeError:
		packs = (course.legacy_content_package,)
	return packs

def _db_connection(registry=None):
	registry = get_registry(registry)
	result = IConnection(registry, None)
	return result

def intid_register(item, registry, intids=None, connection=None):
	intids = component.getUtility(IIntIds) if intids is None else intids
	connection = _db_connection(registry) if connection is None else connection
	if connection is not None:
		connection.add(item)
		intids.register(item, event=False)
		return True
	return False

def _add_2_container(context, item, pacakges=False):
	result = []
	course = ICourseInstance(context)
	container = IPresentationAssetContainer(context)
	container[item.ntiid] = item
	if pacakges:
		for package in get_course_packages(course):
			container = IPresentationAssetContainer(package)
			container[item.ntiid] = item
			result.append(package.ntiid)
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
			item.ntiid = make_asset_ntiid(provided, creator, base=base, extra=idx)
		else:
			stored = registry.queryUtility(provided, name=item.ntiid)
			if stored is not None:
				items[idx] = stored
				created = False
		if created:
			result.append(item)
			item.locked = True # locked
			item.creator = item.creator or creator # set creator before notify
			lifecycleevent.created(item)
			intid_register(item, registry)
			registerUtility(registry, item, provided, name=item.ntiid)
	return result
				
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

class AssetPutViewMixin(object):

	def readInput(self, value=None):
		result = AssetPutViewMixin.readInput(self, value=value)
		result.pop('ntiid', None)
		result.pop('NTIID', None)
		return result

@view_config(context=AssetsPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST')
class AssetPostView(AbstractAuthenticatedView, ModeledContentUploadRequestUtilsMixin):

	content_predicate = IPresentationAsset.providedBy

	@Lazy
	def _course(self):
		parent = self.context.__parent__
		result = ICourseInstance(parent)
		return result

	@Lazy
	def _entry(self):
		result = ICourseCatalogEntry(self._course)
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

	def _check_exists(self, provided, ntiid):
		if self._registry.queryUtility(provided, name=ntiid):
			raise hexc.HTTPUnprocessableEntity(_("Asset already exists."))

	def _handle_package_asset(self, provided, item, creator):
		containers = _add_2_container(self._catalog, item, pacakges=True)
		if provided == INTISlideDeck:
			base = item.ntiid
			# register unique copies
			_canonicalize(item.Slides, creator, base=base, registry=self._registry)
			_canonicalize(item.Videos, creator, base=base, registry=self._registry)
			# register in containers
			for x in chain(item.Slides, item.Videos):
				_add_2_container(self._catalog, x, pacakges=True)
				self._catalog.index(x, container_ntiids=containers,
				  					namespace=containers[0]) # first pkg
		
		self._catalog.index(item, container_ntiids=containers,
				  			namespace=containers[0]) # first pkg
		
	def _handle_asset(self, creator, provided, item):
		if provided in PACKAGE_CONTAINER_INTERFACES:
			self._handle_package_asset(provided, item, creator)

	def _do_call(self):
		creator = self.remoteUser
		content_object = self.readCreateUpdateContentObject(creator)
		content_object.creator = creator.username  # use string
		provided = iface_of_asset(content_object)
		if content_object.ntiid:
			self._check_exists(provided, content_object.ntiid)
		else:
			content_object.ntiid = make_asset_ntiid(provided, creator, extra=self._extra)
		lifecycleevent.created(content_object)
		# register utility
		intid_register(content_object, registry=self._registry)
		registerUtility(self._registry,
						component=content_object,
						provided=provided,
						name=content_object.ntiid)
		# index and post process
		self._handle_asset(creator.username, provided, content_object)
		return content_object
