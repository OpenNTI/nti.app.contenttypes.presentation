#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory as _

import simplejson

from zope import component

from zope.intid import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.appserver.ugd_query_views import _RecursiveUGDView

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode
from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import IMediaRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.externalization import to_external_object

from nti.site.site import get_component_hierarchy_names

from ..utils import is_item_visible
from ..utils.course import get_enrollment_record

from . import VIEW_OVERVIEW_CONTENT
from . import VIEW_OVERVIEW_SUMMARY

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

class OutlineLessonOverviewMixin(object):

	def _get_lesson(self):
		context = self.request.context
		try:
			ntiid = context.LessonOverviewNTIID
			if not ntiid:
				raise hexc.HTTPServerError("Outline does not have a valid lesson overview")

			lesson = component.getUtility(INTILessonOverview, name=ntiid)
			if lesson is None:
				raise hexc.HTTPNotFound("Cannot find lesson overview")
			return lesson
		except AttributeError:
			raise hexc.HTTPServerError("Outline does not have a lesson overview attribute")

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineContentNode,
			 request_method='GET',
			 permission=nauth.ACT_READ,
			 renderer='rest',
			 name=VIEW_OVERVIEW_CONTENT)
class OutlineLessonOverviewView(AbstractAuthenticatedView,
								OutlineLessonOverviewMixin):

	def __call__(self):
		lesson = self._get_lesson()
		external = to_external_object(lesson, name="render")
		external.lastModified = external[LAST_MODIFIED] = lesson.lastModified
		return external

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineContentNode,
			 request_method='GET',
			 permission=nauth.ACT_READ,
			 renderer='rest',
			 name=VIEW_OVERVIEW_SUMMARY)
class OutlineLessonOverviewSummaryView(_RecursiveUGDView,
									   OutlineLessonOverviewMixin):

	_DEFAULT_BATCH_SIZE = None
	_DEFAULT_BATCH_START = 0

	def __call__(self):
		lesson = self._get_lesson()
		result = LocatedExternalDict()
		result[ CLASS ] = 'OverviewGroupSummary'
		self.user = self.remoteUser

		for lesson_group in lesson.items:
			for item in lesson_group.items:
				ugd_count = 0
				# With older content, we're not sure where the UGD
				# may hang; so summarize per item.
				for ntiid_field in ('ntiid', 'target_ntiid'):
					self.ntiid = getattr(item, ntiid_field, None)
					if self.ntiid:
						container_ntiids = ()
						try:
							ugd_results = super(OutlineLessonOverviewSummaryView, self).__call__()
							container_ntiids = ugd_results.get('Items', ())
							ugd_count += len(container_ntiids)
						except hexc.HTTPNotFound:
							pass  # Empty
				result[ item.ntiid ] = item_results = {}
				item_results[ CLASS ] = 'OverviewItemSummary'
				item_results['ItemCount'] = ugd_count
		return result

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_config(context=ICourseInstanceEnrollment)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_READ,
			   request_method='GET',
			   name='MediaByOutlineNode')  # See decorators
class MediaByOutlineNodeDecorator(AbstractAuthenticatedView):

	def _outline_nodes(self, course):
		result = []
		def _recur(node):
			if ICourseOutlineContentNode.providedBy(node):
				if node.src and node.ContentNTIID:
					result.append(node)
			for child in node.values():
				_recur(child)

		outline = course.Outline
		if outline is not None:
			_recur(outline)
		return result

	def _do_legacy(self, course, record):
		result = None
		index_filename = "video_index.json"
		bundle = course.ContentPackageBundle
		for package in bundle.ContentPackages:
			sibling_key = package.does_sibling_entry_exist(index_filename)
			if not sibling_key:
				continue
			else:
				index_text = package.read_contents_of_sibling_entry(index_filename)
				if isinstance(index_text, bytes):
					index_text = index_text.decode('utf-8')
				result = simplejson.loads(index_text)
				break

		result = LocatedExternalDict() if not result else result
		return result

	def _do_current(self, course, record):
		result = LocatedExternalDict()
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)

		items = result[ITEMS] = {}
		containers = result['Containers'] = {}
		
		nodes = self._outline_nodes(course)
		namespaces = {node.src for node in nodes}
		ntiids = {node.ContentNTIID for node in nodes}
		result['ContainerOrder'] = [node.ContentNTIID for node in nodes]
		
		sites = get_component_hierarchy_names()
		for group in catalog.search_objects(
								namespace=namespaces,
								provided=INTICourseOverviewGroup,
								sites=sites):

			for item in group.Items:
				# ignore non media items
				if 	not IMediaRef.providedBy(item) and \
					not INTIMedia.providedBy(item) and \
					not INTISlideDeck.providedBy(item):
					continue

				# check visibility
				if IVisible.providedBy(item):
					if not is_item_visible(item, self.remoteUser, record=record):
						continue
					else:
						item = INTIMedia(item, None)

				# check if ref was valid
				uid = intids.queryId(item) if item is not None else None
				if uid is None:
					continue

				# set content containers
				for ntiid in catalog.get_containers(uid):
					if ntiid in ntiids:
						containers.setdefault(ntiid, [])
						containers[ntiid].append(item.ntiid)
				items[item.ntiid] = to_external_object(item)

		for item in catalog.search_objects(
								container_ntiids=ntiids,
								provided=INTISlideDeck,
								container_all_of=False,
								sites=sites):
			uid = intids.getId(item)
			for ntiid in catalog.get_containers(uid):
				if ntiid in ntiids:
					containers.setdefault(ntiid, [])
					containers[ntiid].append(item.ntiid)
			items[item.ntiid] = to_external_object(item)

		result['Total'] = result['ItemCount'] = len(items)
		return result

	def __call__(self):
		course = ICourseInstance(self.request.context)
		record = get_enrollment_record(course, self.remoteUser)
		if record is None:
			raise hexc.HTTPForbidden(_("Must be enrolled in a course."))

		if ILegacyCourseInstance.providedBy(course):
			result = self._do_legacy(course, record)
		else:
			self.request.no_acl_decoration = True
			result = self._do_current(course, record)
		return result
