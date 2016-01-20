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

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from zope.traversing.interfaces import IEtcNamespace

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.internalization import read_body_as_external_object
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.contenttypes.presentation import iface_of_thing

from nti.app.contenttypes.presentation.synchronizer import can_be_removed
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import remove_and_unindex_course_assets
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.contenttypes.presentation.utils import yield_sync_courses
from nti.app.contenttypes.presentation.utils import remove_presentation_asset

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.common.string import TRUE_VALUES
from nti.common.maps import CaseInsensitiveDict

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_hierarchy

from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver import authorization as nauth
from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.intid.common import removeIntId

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import remove_transaction_history

from nti.site.utils import unregisterUtility
from nti.site.interfaces import IHostPolicyFolder
from nti.site.site import get_site_for_site_names

from nti.traversal.traversal import find_interface

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
	ntiids = values.get('ntiid') or	values.get('ntiids')
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

		self.request.acl_decoration = False
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
		course_ifaces = _course_asset_interfaces()

		total = 0
		items = result[ITEMS] = {}
		catalog = get_library_catalog()
		for course in yield_sync_courses(ntiids):
			folder = find_interface(course, IHostPolicyFolder, strict=False)
			site = get_site_for_site_names((folder.__name__,))
			with current_site(site):
				registry = component.getSiteManager()
				entry = ICourseCatalogEntry(course)
				removed = items[entry.ntiid] = []

				# remove registered assets
				removed.extend(remove_and_unindex_course_assets(
													container_ntiids=entry.ntiid,
												 	course=course,
												 	catalog=catalog,
												 	force=force))
				# remove last mod keys
				clear_namespace_last_modified(course, catalog)

				# remove anything left in containers
				container = IPresentationAssetContainer(course)
				for ntiid, item in list(container.items()):  # mutating
					provided = iface_of_thing(item)
					if provided in course_ifaces and can_be_removed(item, force=force):
						container.pop(ntiid, None)
						remove_presentation_asset(item, registry, catalog)
						removed.append(item)

				# remove all transactions
				for obj in removed:
					remove_transaction_history(obj)
				# keep total
				total += len(removed)
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
			result['SyncTime'] = time.time() - now
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

	def _registered_assets(self, registry):
		for iface in _course_asset_interfaces():
			for ntiid, asset in list(registry.getUtilitiesFor(iface)):
				yield ntiid, asset

	def _site_registry(self, site_name):
		hostsites = component.getUtility(IEtcNamespace, name='hostsites')
		folder = hostsites[site_name]
		registry = folder.getSiteManager()
		return registry

	def _course_assets(self, course):
		ifaces = _course_asset_interfaces()
		container = IPresentationAssetContainer(course)
		for key, value in list(container.items()):  # mutating
			provided = iface_of_thing(value)
			if provided in ifaces:
				yield key, value, container

	def _do_call(self, result):
		registered = 0
		items = result[ITEMS] = []

		sites = set()
		master = set()
		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)

		# clean containers by removing those assets that either
		# don't have an intid or cannot be found in the registry
		for course in yield_sync_courses():
			# check every object in the course
			folder = find_interface(course, IHostPolicyFolder, strict=False)
			sites.add(folder.__name__)
			for ntiid, asset, container in self._course_assets(course):
				uid = intids.queryId(asset)
				provided = iface_of_thing(asset)
				if uid is None:
					container.pop(ntiid, None)
					remove_transaction_history(asset)
				elif component.queryUtility(provided, name=ntiid) is None:
					catalog.unindex(uid)
					removeIntId(asset)
					container.pop(ntiid, None)
					remove_transaction_history(asset)
				else:
					master.add(ntiid)

		# unregister those utilities that cannot be found in the course containers
		for site in sites:
			registry = self._site_registry(site)
			for ntiid, asset in self._registered_assets(registry):
				uid = intids.queryId(asset)
				provided = iface_of_thing(asset)
				if uid is None or ntiid not in master:
					remove_transaction_history(asset)
					unregisterUtility(registry,
									  name=ntiid,
								   	  provided=provided)
					if uid is not None:
						catalog.unindex(uid)
						removeIntId(asset)

					items.append({
						'IntId':uid,
						NTIID:ntiid,
						MIMETYPE:asset.mimeType,
					})
				else:
					registered += 1

		# unindex invalid entries in catalog
		references = catalog.get_references(sites=sites,
										 	provided=_course_asset_interfaces())
		for uid in references or ():
			asset = intids.queryObject(uid)
			if asset is None or not IPresentationAsset.providedBy(asset):
				catalog.unindex(uid)
			else:
				ntiid = asset.ntiid
				provided = iface_of_thing(asset)
				if component.queryUtility(provided, name=ntiid) is None:
					catalog.unindex(uid)
					removeIntId(asset)
					remove_transaction_history(asset)
					items.append({
						'IntId':uid,
						NTIID:ntiid,
						MIMETYPE:asset.mimeType,
					})

		items.sort(key=lambda x:x[NTIID])
		result['Sites'] = list(sites)
		result['TotalContainedAssets'] = len(master)
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
			folder = find_interface(course, IHostPolicyFolder, strict=False)
			site = get_site_for_site_names((folder.__name__,))
			with current_site(site):
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
			result['SyncTime'] = time.time() - now
		return result

@view_config(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=IDataserverFolder,
			   permission=nauth.ACT_NTI_ADMIN,
			   name='OutlineObjectCourseResolver')
class OutlineObjectCourseResolverView(AbstractAuthenticatedView):
	"""
	An admin view to fetch the courses associated with a given
	outline object (node/lesson/group/asset), given by an `ntiid`
	param.
	"""

	def _possible_courses(self, course):
		return get_course_hierarchy(course)

	def __call__(self):
		result = LocatedExternalDict()
		result[ITEMS] = items = []
		params = CaseInsensitiveDict(self.request.params)
		ntiid = params.get('ntiid')
		obj = find_object_with_ntiid(ntiid)
		course = find_interface(obj, ICourseInstance, strict=False)

		if course is None:
			course = ICourseInstance(obj, None)

		if course is not None:
			possible_courses = self._possible_courses(course)
			our_outline = course.Outline
			for course in possible_courses:
				if course.Outline == our_outline:
					items.append(course)
		result['ItemCount'] = len(items)
		result['SiteInfo'] = getSite().__name__
		return result
