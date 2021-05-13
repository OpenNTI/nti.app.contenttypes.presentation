#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.container.interfaces import IContained

from nti.contenttypes.courses.interfaces import ICourseSectionExporter
from nti.contenttypes.courses.interfaces import ICourseSectionImporter


class IPresentationAssetProcessor(interface.Interface):
    """
    Adapter to process and handle post/put operations of assets
    """

    def handle(item, context, creator=None, request=None):
        """
        Handle a particular asset

        :param item: Presentation asset
        :param context: Course instance
        :param creator: Item creator
        :param request: web request
        """


class IItemRefValidator(interface.Interface):

    def validate():
        """
        Return whether or not the item reference is valid
        """


class ILessonPublicationConstraintValidator(interface.Interface):

    def validate():
        """
        Raise an exception if the contraint is not valid
        """


class ILessonOverviewsSectionExporter(ICourseSectionExporter):
    pass


class ILessonOverviewsSectionImporter(ICourseSectionImporter):
    pass


class ICoursePresentationAssets(IContained):
    """
    Assets associated with a course.
    """

    def intids():
        pass

    def items():
        pass

    def __getitem__(ntiid):
        pass
    
