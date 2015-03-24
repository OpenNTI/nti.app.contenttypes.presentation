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

from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.externalization import to_external_object

from . import VIEW_OVERVIEW_CONTENT

LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

@view_config( route_name='objects.generic.traversal',
              context=ICourseOutlineContentNode,
              request_method='GET',
              permission=nauth.ACT_READ,
              renderer='rest',
              name=VIEW_OVERVIEW_CONTENT)
class OutlineLessonOverviewView(AbstractAuthenticatedView):
    
    def __call__(self):
        context = self.request.context
        try:
            ntiid = context.LessonOverviewNTIID
            if not ntiid:
                raise hexc.HTTPServerError("Outline does not have a valid lesson overview")
            
            lesson = component.getUtility(INTILessonOverview, name=ntiid) 
            if lesson is None:
                raise hexc.HTTPNotFound("Cannot find lesson overview")
            external = to_external_object(lesson, name="render")
            external.lastModified = external[LAST_MODIFIED] = lesson.lastModified
            return external
        except AttributeError:
            raise hexc.HTTPServerError("Outline does not have a lesson overview attribute")
