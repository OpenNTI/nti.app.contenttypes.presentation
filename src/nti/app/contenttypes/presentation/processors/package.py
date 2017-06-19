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

from nti.app.contenttypes.presentation.processors.mixins import set_creator
from nti.app.contenttypes.presentation.processors.mixins import canonicalize
from nti.app.contenttypes.presentation.processors.mixins import add_to_container
from nti.app.contenttypes.presentation.processors.mixins import get_site_registry
from nti.app.contenttypes.presentation.processors.mixins import get_context_registry

from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset


def handle_slide_deck(item, context, creator, registry=None):
    handle_asset(item, context, creator)
    base = item.ntiid
    # register unique copies
    registry = get_site_registry(registry)
    canonicalize(item.Slides, creator, base=base,
                 registry=registry)
    canonicalize(item.Videos, creator, base=base,
                 registry=registry)
    # register in containers and index
    for x in chain(item.Slides, item.Videos):
        set_creator(x, creator)
        add_to_container(context, x)
    return item


@component.adapter(IPackagePresentationAsset)
@interface.implementer(IPresentationAssetProcessor)
class PackageAssetProcessor(object):

    __slots__ = ()

    def handle(self, item, context, creator=None, request=None):
        return handle_asset(item, context, creator)


@component.adapter(INTISlideDeck)
@interface.implementer(IPresentationAssetProcessor)
class NTISlideDeckProcessor(object):

    __slots__ = ()

    def handle(self, item, context, creator=None, request=None):
        registry = get_context_registry(context)
        return handle_slide_deck(item, context, creator, registry)
