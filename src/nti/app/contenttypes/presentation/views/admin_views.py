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

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import CourseAdminPathAdapter
from nti.app.products.courseware.interfaces import ILegacyCommunityBasedCourseInstance

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.dataserver import authorization as nauth
from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from ..utils import remove_all_utilities

from .. import get_catalog

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
		count = 0
		params = self.request.params
		result = LocatedExternalDict()
		result[ITEMS] = items = {}
		extended = (params.get('all') or u'').lower() in ('true', '1', 'yes', 'y', 't')
		for provided in ALL_PRESENTATION_ASSETS_INTERFACES:
			comps = list(component.getUtilitiesFor(provided))
			count += len(comps)
			if extended:
				items[provided.__name__] = sorted(n for n, _ in comps)
			else:
				items[provided.__name__] = len(comps)
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


	def __call__(self):
		now = time.time()
		result = LocatedExternalDict()
		result[ITEMS] = remove_all_utilities()
		index = get_catalog()
		index.reset()
		result['Elapsed'] = time.time() - now
		return result
