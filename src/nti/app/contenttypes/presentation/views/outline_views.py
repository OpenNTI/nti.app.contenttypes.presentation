#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from pyramid.view import view_config
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.appserver.ugd_query_views import _UGDView as UGDQueryView

from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.externalization import to_external_object

from . import VIEW_OVERVIEW_CONTENT
from . import VIEW_OVERVIEW_SUMMARY

CLASS = StandardExternalFields.CLASS
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
class OutlineLessonOverviewSummaryView(UGDQueryView,
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
					self.ntiid = getattr( item, ntiid_field, None )
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
