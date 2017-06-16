#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import interface

from zope.deprecation import deprecated


class IPresentationAssetProcessor(interface.Interface):

    def handle():
        """
        Return whether or not the item reference is valid
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


deprecated('IPresentationAssetsIndex', 'Use lastest library implementation')
class IPresentationAssetsIndex(interface.Interface):
    pass
