#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import interface

from zope.deprecation import deprecated


deprecated('IPresentationAssetsIndex', 'Use lastest library implementation')
class IPresentationAssetsIndex(interface.Interface):
    pass


class IItemRefValidator(interface.Interface):

    def validate():
        """
        Return whether or not the item reference is valid
        """


class ILessonPublicationConstraintChecker(interface.Interface):

    def is_satisfied(constraint, principal=None):
        """
        Return whether or not a constraint is satisfied.
        """


class ILessonPublicationConstraintValidator(interface.Interface):

    def validate():
        """
        Raise an exception if the contraint is not valid
        """
