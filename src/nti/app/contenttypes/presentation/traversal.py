#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.location.interfaces import LocationError

from pyramid.interfaces import IRequest

from nti.app.contenttypes.presentation.interfaces import ICoursePresentationAssets

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraints

from nti.traversal.traversal import DefaultAdapterTraversable
from nti.traversal.traversal import ContainerAdapterTraversable


@component.adapter(INTILessonOverview, IRequest)
class _LessonOverviewTraversable(DefaultAdapterTraversable):

    def traverse(self, key, _):
        if key == 'PublicationConstraints':
            return ILessonPublicationConstraints(self.context)
        raise LocationError(key)


@component.adapter(ILessonPublicationConstraints, IRequest)
class _LessonPublicationConstraintsTraversable(ContainerAdapterTraversable):

    def traverse(self, key, remaining_path):
        return ContainerAdapterTraversable.traverse(self, key, remaining_path)

def _course_assets_path_adapter(context, request):
    return ICoursePresentationAssets(context)
