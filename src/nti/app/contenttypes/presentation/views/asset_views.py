#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.renderers.interfaces import INoHrefInResponse

from nti.appserver.dataserver_pyramid_views import _GenericGetView as GenericGetView

from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.externalization.externalization import to_external_object

@view_config(context=INTITimeline)
@view_config(context=INTIRelatedWorkRef)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET')
class AssetGetView(GenericGetView):

    def __call__(self):
        result = GenericGetView.__call__(self)
        result = to_external_object(result)
        interface.alsoProvides(result, INoHrefInResponse)
        return result
