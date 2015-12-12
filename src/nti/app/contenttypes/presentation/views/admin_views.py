#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import time

from zope import component

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from zope.intid import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.externalization.internalization import read_body_as_external_object
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.common.string import TRUE_VALUES
from nti.common.maps import CaseInsensitiveDict

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver import authorization as nauth
from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.recorder.record import remove_transaction_history

from nti.site.utils import unregisterUtility

from ..utils import component_registry
from ..utils import yield_sync_courses

from ..synchronizer import synchronize_course_lesson_overview

from .. import iface_of_thing

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE

def _course_asset_interfaces():
	result = []
	for iface in ALL_PRESENTATION_ASSETS_INTERFACES:
		if iface not in PACKAGE_CONTAINER_INTERFACES:
			result.append(iface)
	return result

def _get_course_ntiids(values):
	ntiids = values.get('ntiid') or values.get('ntiids') or \
			 values.get('entry') or values.get('entries') or \
			 values.get('course') or values.get('courses')
	if ntiids and isinstance(ntiids, six.string_types):
		ntiids = ntiids.split()
	return ntiids

def _is_true(v):
	return v and str(v).lower() in TRUE_VALUES

def _read_input(request):
	result = CaseInsensitiveDict()
	if request:
		if request.body:
			values = read_body_as_external_object(request)
		else:
			values = request.params
		result.update(values)
	return result

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='GetCoursePresentationAssets')
class GetCoursePresentationAssetsView(AbstractAuthenticatedView,
							  		  ModeledContentUploadRequestUtilsMixin):

	def __call__(self):
		params = CaseInsensitiveDict(self.request.params)
		ntiids = _get_course_ntiids(params)
		courses = list(yield_sync_courses(ntiids))

		total = 0
		result = LocatedExternalDict()
		result[ITEMS] = items = {}
		for course in courses:
			entry = ICourseCatalogEntry(course)
			container = IPresentationAssetContainer(course)
			items[entry.ntiid] = sorted(container.values(),
										key=lambda x: x.__class__.__name__)
			total += len(items[entry.ntiid])
		result['ItemCount'] = result['Total'] = total
		return result

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='RemoveCourseInaccessibleAssets')
class RemoveCourseInaccessibleAssetsView(AbstractAuthenticatedView,
							  	   		 ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		return _read_input(self.request)

	def _unregister(self, context, provided, name):
		registry = component_registry(context, provided, name)
		if registry is not None:
			result = unregisterUtility(registry,
									   provided=provided,
									   name=name)
			return result
		return False

	def _registered_assets(self, registry):
		for iface in _course_asset_interfaces():
			for ntiid, asset in list(registry.getUtilitiesFor(iface)):
				yield ntiid, asset

	def _contained_assets(self):
		result = {}
		ifaces = _course_asset_interfaces()
		for course in yield_sync_courses():
			container = IPresentationAssetContainer(course)
			for key, value in container.items():
				provided = iface_of_thing(value)
				if provided in ifaces:
					result[key] = (value, container)
		return result

	def _do_call(self, result):
		registry = get_registry()
		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)

		contained = 0
		registered = 0
		items = result[ITEMS] = []
		master = self._contained_assets()

		# clean containers by removing those assets that either
		# don't have an intid or cannot be found in the registry
		for ntiid, data in list(master.items()):
			asset, container = data
			uid = intids.queryId(asset)
			provided = iface_of_thing(asset)
			if uid is None or component.queryUtility(provided, name=ntiid) is None:
				container.pop(ntiid, None)
				remove_transaction_history(asset)
				if uid is not None:
					catalog.unindex(uid)
					intids.unregister(asset)
				master.pop(ntiid)
			else:
				contained += 1

		# unregister those utilities that cannot be found
		# in the course containers
		for ntiid, asset in self._registered_assets(registry):
			uid = intids.queryId(asset)
			provided = iface_of_thing(asset)
			if uid is None or ntiid not in master:
				remove_transaction_history(asset)
				self._unregister(asset, provided=provided, name=ntiid)
				if uid is not None:
					catalog.unindex(uid)
					intids.unregister(asset)
				items.append({
					'IntId':uid,
					NTIID:ntiid,
					MIMETYPE:asset.mimeType,
				})
			else:
				registered += 1

		items.sort(key=lambda x:x[NTIID])
		result['TotalContainedAssets'] = contained
		result['TotalRegisteredAssets'] = registered
		result['Total'] = result['ItemCount'] = len(items)
		return result

	def __call__(self):
		result = LocatedExternalDict()
		endInteraction()
		try:
			self._do_call(result)
		finally:
			restoreInteraction()
		return result

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='SyncCoursePresentationAssets')
class SyncCoursePresentationAssetsView(AbstractAuthenticatedView,
									   ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		return _read_input(self.request)

	def _do_call(self, result):
		values = self.readInput()
		ntiids = _get_course_ntiids(values)
		courses = list(yield_sync_courses(ntiids=ntiids))

		items = result[ITEMS] = []
		for course in courses:
			synchronize_course_lesson_overview(course)
			items.append(ICourseCatalogEntry(course).ntiid)
		return result

	def __call__(self):
		now = time.time()
		result = LocatedExternalDict()
		endInteraction()
		try:
			self._do_call(result)
		finally:
			restoreInteraction()
			result['TimeElapsed'] = time.time() - now
		return result
