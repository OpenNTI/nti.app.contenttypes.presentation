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

from zope.traversing.interfaces import IEtcNamespace

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

from nti.site.utils import unregisterUtility
from nti.site.site import get_component_hierarchy_names

from ..utils.common import yield_sync_courses

from ..subscribers import can_be_removed
from ..subscribers import clear_course_assets
from ..subscribers import clear_namespace_last_modified
from ..subscribers import remove_and_unindex_course_assets
from ..subscribers import synchronize_course_lesson_overview

from .. import iface_of_thing

ITEMS = StandardExternalFields.ITEMS

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

		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)

		total = 0
		result = LocatedExternalDict()
		result[ITEMS] = items = {}
		sites = get_component_hierarchy_names()
		asset_interfaces = _course_asset_interfaces()
		for course in courses:
			entry = ICourseCatalogEntry(course)
			objects = catalog.search_objects(intids=intids,
											 provided=asset_interfaces,
											 container_ntiids=entry.ntiid,
											 sites=sites)
			items[entry.ntiid] = sorted(objects or (),
										key=lambda x: x.__class__.__name__)
			total += len(items[entry.ntiid])
		result['ItemCount'] = result['Total'] = total
		return result

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='ResetCoursePresentationAssets')
class ResetCoursePresentationAssetsView(AbstractAuthenticatedView,
							  	  		ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		return _read_input(self.request)

	def _do_call(self, result):
		values = self.readInput()
		ntiids = _get_course_ntiids(values)
		force = _is_true(values.get('force'))
		courses = list(yield_sync_courses(ntiids))
		
		total = 0
		items = result[ITEMS] = {}
		catalog = get_library_catalog()
		sites = get_component_hierarchy_names()
		for course in courses:
			entry = ICourseCatalogEntry(course)
			removed = remove_and_unindex_course_assets(container_ntiids=entry.ntiid,
											 		   course=course,
											 		   catalog=catalog,
											 		   force=force,
											 		   sites=sites)
			items[entry.ntiid] = removed
			clear_namespace_last_modified(course, catalog)

		result['Total'] = total
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
	
	def _unregister(self, sites_names, provided, name):
		result = False
		reverse = list(sites_names)
		reverse.reverse()
		hostsites = component.getUtility(IEtcNamespace, name='hostsites')
		for site_name in reverse:
			try:
				folder = hostsites[site_name]
				registry = folder.getSiteManager()
				result = unregisterUtility(registry,
										   provided=provided,
										   name=name) or result
			except KeyError:
				pass
		return result

	def _registered_assets(self, registry):
		for iface in _course_asset_interfaces():
			for ntiid, asset in list(registry.getUtilitiesFor(iface)):
				yield ntiid, asset

	def _contained_assets(self):
		result = []
		asset_interfaces = _course_asset_interfaces()
		for course in yield_sync_courses():
			container = IPresentationAssetContainer(course, None) or {}
			for key, value in container.items():
				provided = iface_of_thing(value)
				if provided in asset_interfaces:
					result.append((container, key, value))
		return result

	def _do_call(self, result):
		registry = get_registry()
		catalog = get_library_catalog()
		sites = get_component_hierarchy_names()
		intids = component.getUtility(IIntIds)

		registered = 0
		items = result[ITEMS] = []
		references = catalog.get_references(sites=sites,
										 	provided=_course_asset_interfaces())

		for ntiid, asset in self._registered_assets(registry):
			uid = intids.queryId(asset)
			provided = iface_of_thing(asset)
			if uid is None:
				items.append(repr((provided.__name__, ntiid)))
				self._unregister(sites, provided=provided, name=ntiid)
			elif uid not in references:
				items.append(repr((provided.__name__, ntiid, uid)))
				self._unregister(sites, provided=provided, name=ntiid)
				intids.unregister(asset)
			registered += 1

		contained = set()
		for container, ntiid, asset in self._contained_assets():
			uid = intids.queryId(asset)
			provided = iface_of_thing(asset)
			if 	uid is None or uid not in references or \
				component.queryUtility(provided, name=ntiid) is None:
				container.pop(ntiid, None)
				self._unregister(sites, provided=provided, name=ntiid)
				if uid is not None:
					catalog.unindex(uid)
					intids.unregister(asset)
			contained.add(ntiid)

		result['TotalRemoved'] = len(items)
		result['TotalRegisteredAssets'] = registered
		result['TotalContainedAssets'] = len(contained)
		result['TotalCatalogedAssets'] = len(references)
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

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='RemoveAllCoursesPresentationAssets')
class RemoveAllCoursesPresentationAssetsView(RemoveCourseInaccessibleAssetsView):

	def _do_call(self, result):
		values = self.readInput()
		registry = get_registry()
		catalog = get_library_catalog()
		force = _is_true(values.get('force'))
		sites = get_component_hierarchy_names()
		intids = component.getUtility(IIntIds)

		registered = 0
		references = set()
		result_set = catalog.search_objects(sites=sites,
										 	provided=_course_asset_interfaces())
		for uid, asset in result_set.iter_pairs():
			if can_be_removed(asset, force=force):
				catalog.unindex(uid)
			references.add(uid)

		for ntiid, asset in self._assets(registry):
			if not can_be_removed(asset, force=force):
				continue
			uid = intids.queryId(asset)
			provided = iface_of_thing(asset)
			self._unregister(sites, provided=provided, name=ntiid)
			if uid is not None:
				intids.unregister(asset)
			registered += 1

		for course in yield_sync_courses():
			clear_course_assets(course)
			clear_namespace_last_modified(course, catalog)

		result['TotalRegisteredAssets'] = registered
		result['TotalCatalogedAssets'] = len(references)
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
