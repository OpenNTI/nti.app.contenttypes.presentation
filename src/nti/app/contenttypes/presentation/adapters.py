#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.traversal.traversal import find_interface

@interface.implementer(ICourseInstance)
@component.adapter(INTICourseOverviewGroup)
def _course_overview_group_to_course(group):
	return find_interface(group, ICourseInstance, strict=False)

@interface.implementer(INTILessonOverview)
@component.adapter(INTICourseOverviewGroup)
def _lesson_overview_to_course(group):
	return find_interface(group, ICourseInstance, strict=False)
