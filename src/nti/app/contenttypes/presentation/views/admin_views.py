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

from zope.intid import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import CourseAdminPathAdapter
from nti.app.products.courseware.interfaces import ILegacyCommunityBasedCourseInstance

from nti.common.maps import CaseInsensitiveDict

from nti.contentlibrary.indexed_data import get_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth
from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from ..subscribers import remove_and_unindex_course_assets

ITEMS = StandardExternalFields.ITEMS

def _parse_courses(values):
	ntiids = values.get('ntiid') or values.get('ntiids') or \
			 values.get('entry') or values.get('entries') or \
			 values.get('course') or values.get('courses')
	if not ntiids:
		raise hexc.HTTPUnprocessableEntity(detail='No course entry identifier')

	if isinstance(ntiids, six.string_types):
		ntiids = ntiids.split()

	result = []
	for ntiid in ntiids:
		context = find_object_with_ntiid(ntiid)
		if context is None:
			try:
				catalog = component.getUtility(ICourseCatalog)
				entry = catalog.getCatalogEntry(ntiid)
				course = ICourseInstance(entry, None)
				if 	course is not None and \
					not ILegacyCommunityBasedCourseInstance.providedBy(course):
					result.append(course)
			except KeyError:
				pass
		else:
			course = ICourseInstance(context, None)
			if course is not None:
				result.append(course)
	return result

def _get_all_courses():
	result = []
	catalog = component.getUtility(ICourseCatalog)
	for entry in catalog.iterCatalogEntries():
		course = ICourseInstance(entry, None)
		if 	course is not None and \
			not ILegacyCommunityBasedCourseInstance.providedBy(course):
			result.append(course)
	return result

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='GetPresentationAssets')
class GetPresentationAssetsView(AbstractAuthenticatedView,
							  	ModeledContentUploadRequestUtilsMixin):


	def __call__(self):
		params = CaseInsensitiveDict(self.request.params)
		courses = _parse_courses(params)
		if not courses:
			raise hexc.HTTPUnprocessableEntity('Must specify a valid course')
		
		count = 0
		catalog = get_catalog()
		intids = component.getUtility(IIntIds)
		
		result = LocatedExternalDict()
		result[ITEMS] = items = []
		for course in courses:
			entry = ICourseCatalogEntry(course)
			for item in catalog.search_objects(intids=intids,
									  		   container_ntiids=entry.ntiid):
				count += 1
				items.append(item)
		result['Total'] = count
		return result

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='ResetPresentationAssets')
class ResetPresentationAssetsView(AbstractAuthenticatedView,
							  	  ModeledContentUploadRequestUtilsMixin):


	def readInput(self, value=None):
		values = super(ResetPresentationAssetsView, self).readInput(self, value=value)
		return CaseInsensitiveDict(values)

	def __call__(self):
		now = time.time()
		values = self.readInput()
		courses = _parse_courses(values)
		if not courses:
			raise hexc.HTTPUnprocessableEntity('Must specify a valid course')

		total = 0
		catalog = get_catalog()
		result = LocatedExternalDict()
		for course in courses:
			entry = ICourseCatalogEntry(course)
			total += remove_and_unindex_course_assets(container_ntiids=entry.ntiid,
											 		  course=course,
											 		  catalog=catalog)
		result['Total'] = total
		result['Elapsed'] = time.time() - now
		return result
