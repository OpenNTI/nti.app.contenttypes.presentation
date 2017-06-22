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

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.processors.asset import handle_asset

from nti.app.contenttypes.presentation.processors.mixins import BaseAssetProcessor

from nti.app.contenttypes.presentation.processors.mixins import canonicalize
from nti.app.contenttypes.presentation.processors.mixins import get_context_registry

from nti.contenttypes.presentation.interfaces import INTIMediaRoll


def handle_media_roll(item, context, creator, request=None):
    handle_asset(item, context, creator, request)
    # register unique copies
    registry = get_context_registry(context)
    canonicalize(item.Items or (), creator,
                 base=item.ntiid,
                 registry=registry)
    for x in item or ():
        proc = IPresentationAssetProcessor(x)
        proc.handle(item, context, creator, request)


@component.adapter(INTIMediaRoll)
@interface.implementer(IPresentationAssetProcessor)
class MediaRollProcessor(BaseAssetProcessor):

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_media_roll(item, context, creator, request)
