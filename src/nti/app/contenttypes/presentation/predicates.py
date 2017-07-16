#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.contenttypes.presentation.lesson import constraints_for_lesson

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.metadata.predicates import BasePrincipalObjects


def yield_lesson_constraints(asset):
    constraints = constraints_for_lesson(asset, False)
    if constraints is not None:
        for obj in constraints.values():
            yield obj


@component.adapter(ISystemUserPrincipal)
class _SystemPresentationAssets(BasePrincipalObjects):

    def iter_objects(self):
        for _, asset in component.getUtilitiesFor(IPresentationAsset):
            if self.is_system_username(self.creator(asset)):
                if INTILessonOverview.providedBy(asset):
                    for item in yield_lesson_constraints(asset):
                        if self.is_system_username(self.creator(item)):
                            yield item
                yield asset


@component.adapter(IUser)
class _UserPresentationAssets(BasePrincipalObjects):

    def iter_objects(self):
        for _, asset in component.getUtilitiesFor(IPresentationAsset):
            if self.creator(asset) == self.username:
                if INTILessonOverview.providedBy(asset):
                    for item in yield_lesson_constraints(asset):
                        if self.creator(item) == self.username:
                            yield item
                yield asset
