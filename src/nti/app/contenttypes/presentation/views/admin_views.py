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

from zope.traversing.interfaces import IEtcNamespace

from zope.intid import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import CourseAdminPathAdapter
from nti.app.products.courseware.interfaces import ILegacyCommunityBasedCourseInstance

from nti.common.maps import CaseInsensitiveDict

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.dataserver import authorization as nauth
from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.utils import unregisterUtility
from nti.site.site import get_component_hierarchy_names

from ..subscribers import remove_and_unindex_course_assets

from .. import iface_of_thing

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

		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)

		result = LocatedExternalDict()
		result[ITEMS] = items = []
		sites = get_component_hierarchy_names()
		for course in courses:
			entry = ICourseCatalogEntry(course)
			objects = catalog.search_objects(intids=intids,
											 container_ntiids=entry.ntiid,
											 sites=sites)

			items.extend(sorted(objects or (), key=lambda x: x.__class__.__name__))
		result['ItemCount'] = result['Total'] = len(items)
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
		catalog = get_library_catalog()
		result = LocatedExternalDict()
		sites = get_component_hierarchy_names()
		for course in courses:
			entry = ICourseCatalogEntry(course)
			total += remove_and_unindex_course_assets(container_ntiids=entry.ntiid,
											 		  course=course,
											 		  catalog=catalog,
											 		  sites=sites)
		result['Total'] = total
		result['Elapsed'] = time.time() - now
		return result

@view_config(context=IDataserverFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='RemoveInaccessibleAssets')
class RemoveInaccessibleAssetsView(AbstractAuthenticatedView,
							  	   ModeledContentUploadRequestUtilsMixin):

	def unregister(self, sites_names, provided, name):
		hostsites = component.getUtility(IEtcNamespace, name='hostsites')
		for site_name in sites_names:
			try:
				folder = hostsites[site_name]
				registry = folder.getSiteManager()
				unregisterUtility(registry, provided=provided, name=name)
			except KeyError:
				pass

	def __call__(self):
		now = time.time()
		registry = get_registry()
		catalog = get_library_catalog()
		sites = get_component_hierarchy_names()
		intids = component.getUtility(IIntIds)

		result = LocatedExternalDict()
		items = result[ITEMS] = []

		removed = catalog.family.IF.LFSet()
		references = catalog.get_references(sites=sites,
										 	provided=ALL_PRESENTATION_ASSETS_INTERFACES)

		registered = list(registry.getUtilitiesFor(IPresentationAsset))
		for ntiid, asset in registered:
			uid = intids.queryId(asset)
			provided = iface_of_thing(asset)
			if uid is None:
				items.append(repr((provided.__name__, ntiid)))
				self.unregister(sites, provided=provided, name=ntiid)
			elif uid not in references:
				removed.add(uid)
				items.append(repr((provided.__name__, ntiid, uid)))
				self.unregister(sites, provided=provided, name=ntiid)
				intids.unregister(asset)

		result['TotalRemoved'] = len(items)
		result['TimeElapsed'] = time.time() - now
		result['TotalCatalogedAssets'] = len(references)
		result['TotalRegisteredAssets'] = len(registered)
		return result
