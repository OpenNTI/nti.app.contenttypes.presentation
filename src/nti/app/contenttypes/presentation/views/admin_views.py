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

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary.views.sync_views import _AbstractSyncAllLibrariesView

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.contenttypes.presentation.synchronizer import can_be_removed
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import remove_and_unindex_course_assets
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.contenttypes.presentation.utils import yield_sync_courses
from nti.app.contenttypes.presentation.utils import remove_presentation_asset

from nti.app.contenttypes.presentation.utils.common import remove_all_invalid_assets
from nti.app.contenttypes.presentation.utils.common import remove_course_inaccessible_assets

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.common.maps import CaseInsensitiveDict

from nti.common.string import is_true

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_hierarchy

from nti.contenttypes.presentation.interfaces import ICoursePresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver import authorization as nauth
from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import remove_transaction_history

from nti.site.interfaces import IHostPolicyFolder

from nti.site.hostpolicy import get_host_site

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

def _get_course_ntiids(values):
	ntiids = values.get('ntiid') or	values.get('ntiids')
	if ntiids and isinstance(ntiids, six.string_types):
		ntiids = ntiids.split()
	return ntiids

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
		result[ITEM_COUNT] = result[TOTAL] = total
		return result

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='ResetCoursePresentationAssets')
class ResetCoursePresentationAssetsView(_AbstractSyncAllLibrariesView):

	def _do_call(self):
		values = self.readInput()
		ntiids = _get_course_ntiids(values)
		force = is_true(values.get('force'))

		total = 0
		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		catalog = get_library_catalog()
		for course in yield_sync_courses(ntiids):
			folder = find_interface(course, IHostPolicyFolder, strict=False)
			with current_site(get_host_site(folder.__name__)):
				removed = []

				registry = folder.getSiteManager()
				entry = ICourseCatalogEntry(course)

				# remove registered assets
				removed.extend(remove_and_unindex_course_assets(
													container_ntiids=entry.ntiid,
												 	course=course,
												 	catalog=catalog,
												 	registry=registry,
												 	force=force))
				# remove last mod keys
				clear_namespace_last_modified(course, catalog)

				# remove anything left in containers
				container = IPresentationAssetContainer(course)
				for ntiid, item in tuple(container.items()):  # mutating
					if 		ICoursePresentationAsset.providedBy(item) \
						and can_be_removed(item, force=force):
						container.pop(ntiid, None)
						remove_presentation_asset(item, registry, catalog)
						removed.append(item)

				# remove all transactions
				for obj in removed:
					remove_transaction_history(obj)
				# keep total
				total += len(removed)

				# only return ntiids
				items[entry.ntiid] = [x.ntiid for x in removed]

		result[ITEM_COUNT] = result[TOTAL] = total
		return result

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_SYNC_LIBRARY,
			   name='SyncCoursePresentationAssets')
class SyncCoursePresentationAssetsView(_AbstractSyncAllLibrariesView):

	def _do_call(self):
		now = time.time()
		values = self.readInput()
		result = LocatedExternalDict()
		ntiids = _get_course_ntiids(values)
		courses = list(yield_sync_courses(ntiids=ntiids))
		items = result[ITEMS] = []
		for course in courses:
			folder = find_interface(course, IHostPolicyFolder, strict=False)
			with current_site(get_host_site(folder.__name__)):
				synchronize_course_lesson_overview(course)
				items.append(ICourseCatalogEntry(course).ntiid)
		result['SyncTime'] = time.time() - now
		return result

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_SYNC_LIBRARY,
			   name='RemoveCourseInaccessibleAssets')
class RemoveCourseInaccessibleAssetsView(AbstractAuthenticatedView,
							  	   		 ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		return _read_input(self.request)

	def __call__(self):
		endInteraction()
		try:
			result = remove_course_inaccessible_assets()
		finally:
			restoreInteraction()
		return result

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_SYNC_LIBRARY,
			   name='RemoveInvalidPresentationAssets')
class RemoveInvalidPresentationAssetsView(AbstractAuthenticatedView,
									  	  ModeledContentUploadRequestUtilsMixin):

	def __call__(self):
		result = LocatedExternalDict()
		endInteraction()
		try:
			result[ITEMS] = dict(remove_all_invalid_assets())
		finally:
			restoreInteraction()
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
		course = ICourseInstance(obj, None) if course is None else course
		if course is not None:
			possible_courses = self._possible_courses(course)
			our_outline = course.Outline
			for course in possible_courses:
				if course.Outline == our_outline:
					items.append(course)
		result[TOTAL] = result[ITEM_COUNT] = len(items)
		result['Site'] = result['SiteInfo'] = getSite().__name__
		return result
