#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from itertools import chain

from zope import component
from zope import interface

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.processors.asset import handle_asset

from nti.app.contenttypes.presentation.processors.mixins import BaseAssetProcessor

from nti.app.contenttypes.presentation.processors.mixins import canonicalize
from nti.app.contenttypes.presentation.processors.mixins import get_context_registry

from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset


def handle_slide_deck(item, context, creator, request=None):
    handle_asset(item, context, creator, request)
    base = item.ntiid
    # register unique copies
    registry = get_context_registry(context)
    canonicalize(item.Slides, creator, base=base,
                 registry=registry)
    canonicalize(item.Videos, creator, base=base,
                 registry=registry)
    # register in containers and index
    for x in chain(item.Slides, item.Videos):
        proc = IPresentationAssetProcessor(x)
        proc.handle(x, context, creator, request)
    return item


@component.adapter(IPackagePresentationAsset)
@interface.implementer(IPresentationAssetProcessor)
class PackageAssetProcessor(BaseAssetProcessor):

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_asset(item, context, creator)


@component.adapter(INTISlideDeck)
@interface.implementer(IPresentationAssetProcessor)
class NTISlideDeckProcessor(BaseAssetProcessor):

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_slide_deck(item, context, creator, request)
