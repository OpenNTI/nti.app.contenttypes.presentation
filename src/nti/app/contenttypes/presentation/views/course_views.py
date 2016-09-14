#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.intid.interfaces import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.presentation.views import VIEW_ASSETS

from nti.common.maps import CaseInsensitiveDict

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation.interfaces import IConcreteAsset

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import LocatedExternalDict
from nti.externalization.externalization import StandardExternalFields

from nti.site.site import get_component_hierarchy_names

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name=VIEW_ASSETS,
			   request_method='GET',
			   permission=nauth.ACT_CONTENT_EDIT)
class CoursePresentationAssetsView(AbstractAuthenticatedView):

	def _get_mimeTypes(self):
		params = CaseInsensitiveDict(self.request.params)
		result = params.get('accept') or params.get('mimeType')
		if result:
			result = set(result.split(','))
		return result or ()

	def _pkg_containers(self, pacakge):
		result = []
		def recur(unit):
			for child in unit.children or ():
				recur(child)
			result.append(unit.ntiid)
		recur(pacakge)
		return result

	def _course_containers(self, course):
		result = set()
		entry = ICourseCatalogEntry(course)
		for pacakge in get_course_packages(course):
			result.update(self._pkg_containers(pacakge))
		result.add(entry.ntiid)
		return result

	def _check_mimeType(self, item, mimeTypes=()):
		if not mimeTypes:
			return True
		else:
			mt = getattr(item, 'mimeType', None) or getattr(item, 'mime_type', None)
			if mt in mimeTypes:
				return True
		return False

	def _yield_course_items(self, course, mimeTypes=()):
		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)
		container_ntiids = self._course_containers(course)
		for item in catalog.search_objects(intids=intids,
										   container_all_of=False,
										   container_ntiids=container_ntiids,
										   sites=get_component_hierarchy_names(),
										   provided=ALL_PRESENTATION_ASSETS_INTERFACES):
			concrete = IConcreteAsset(item, item)
			if self._check_mimeType(concrete, mimeTypes):
				yield concrete
			elif self._check_mimeType(item, mimeTypes):
				yield item

	def _do_call(self):
		result = LocatedExternalDict()
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		self.request.acl_decoration = False  # decoration

		mimeTypes = self._get_mimeTypes()
		course = ICourseInstance(self.context)

		result[ITEMS] = items = []
		items.extend(x for x in self._yield_course_items(course, mimeTypes))
		items.sort()  # natural order
		lastModified = reduce(lambda x, y: max(x, getattr(y, 'lastModified', 0)), items, 0)
		result[ITEM_COUNT] = result[TOTAL] = len(items)
		result[LAST_MODIFIED] = result.lastModified =lastModified
		return result

	def __call__(self):
		return self._do_call()
