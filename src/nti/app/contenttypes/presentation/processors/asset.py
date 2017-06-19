#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.app.authentication import get_remote_user

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.processors.mixins import set_creator
from nti.app.contenttypes.presentation.processors.mixins import add_to_container

from nti.contenttypes.presentation.interfaces import IPresentationAsset


def handle_asset(item, context, creator=None):
    creator = creator or get_remote_user()
    set_creator(item, creator)
    # If we don't have parent, use course.
    if item.__parent__ is None:
        item.__parent__ = context
    add_to_container(context, item)
    return item


@component.adapter(IPresentationAsset)
@interface.implementer(IPresentationAssetProcessor)
class PresentationAssetProcessor(object):

    __slots__ = ()

    def handle(self, item, context, creator=None, request=None):
        return handle_asset(item, context, creator)
