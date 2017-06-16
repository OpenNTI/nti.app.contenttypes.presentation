#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import interface


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
