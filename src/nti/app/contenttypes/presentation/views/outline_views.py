#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.contenttypes.courses.interfaces import ICourseOutline

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

from . import VIEW_OVERVIEW_CONTENT

@view_config( route_name='objects.generic.traversal',
              context=ICourseOutline,
              request_method='GET',
              permission=nauth.ACT_READ,
              renderer='rest',
              name=VIEW_OVERVIEW_CONTENT)
class OutlineLessonOverviewView(AbstractAuthenticatedView):
    
    def __call__(self):
        context = self.request.context
        try:
            if not context.LessonOverviewNTIID:
                raise hexc.HTTPServerError("Outline does not have a valid lesson overview")
            
            lesson = find_object_with_ntiid(context.LessonOverviewNTIID)
            if lesson is None:
                raise hexc.HTTPNotFound("Cannot find lesson overview")
            external = to_external_object(context, name="render")
            return external
        except AttributeError:
            raise hexc.HTTPServerError("Outline does not have a lesson overview attribute")
