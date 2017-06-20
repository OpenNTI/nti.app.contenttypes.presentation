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

from nti.app.contenttypes.presentation.processors.mixins import set_creator
from nti.app.contenttypes.presentation.processors.mixins import canonicalize
from nti.app.contenttypes.presentation.processors.mixins import add_to_container
from nti.app.contenttypes.presentation.processors.mixins import get_site_registry
from nti.app.contenttypes.presentation.processors.mixins import get_context_registry

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck

from nti.site.interfaces import IHostPolicyFolder


def get_slide_deck_for_video(item, context):
    """
    When inserting a video, iterate through any slide decks looking
    for a collision, if so, we want to index by our slide deck.
    """
    folder = IHostPolicyFolder(context)
    packages = list(get_course_packages(context))
    if packages:
        namespace = [x.ntiid for x in packages]
        target = (item.ntiid,)
        if INTIMediaRef.providedBy(item):
            target = (item.ntiid, getattr(item, 'target', ''))
        catalog = get_library_catalog()
        slide_decks = catalog.search_objects(provided=INTISlideDeck,
                                             namespace=namespace,
                                             sites=folder.__name__)
        for slide_deck in slide_decks or ():
            for video in slide_deck.videos or ():
                if video.video_ntiid in target:
                    return slide_deck
    return None


def handle_video(item, context, creator, request=None):
    """
    Check if the given video is actually a slidedeck video and handle
    the slidedeck accordingly.
    """
    slide_deck = get_slide_deck_for_video(item, context)
    if slide_deck is not None:
        return handle_asset(slide_deck, context, creator)
    # Just a video
    if INTIVideo.providedBy(item):
        handle_asset(item, context, creator)
    else:
        # media refs need this path
        handle_asset(item, context, creator)


def handle_media_roll(item, context, creator, registry=None):
    set_creator(item, creator)
    add_to_container(context, item)
    # register unique copies
    registry = get_site_registry(registry)
    canonicalize(item.Items or (), creator,
                 base=item.ntiid,
                 registry=registry)
    for x in item or ():
        set_creator(x, creator)
        add_to_container(context, x)


@component.adapter(INTIMediaRoll)
@interface.implementer(IPresentationAssetProcessor)
class MediaRollProcessor(object):

    def __init__(self, asset=None):
        self.asset = asset

    def handle(self, item, context, creator=None, request=None):
        registry = get_context_registry(context)
        item = self.asset if item is None else item
        return handle_media_roll(item, context, creator, registry)


@component.adapter(INTIVideo)
@interface.implementer(IPresentationAssetProcessor)
class NTIVideoProcessor(object):

    def __init__(self, asset=None):
        self.asset = asset

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_video(item, context, creator, request)


@component.adapter(INTIMediaRef)
@interface.implementer(IPresentationAssetProcessor)
class NTIMediaRefRollProcessor(object):

    def __init__(self, asset=None):
        self.asset = asset

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_video(item, context, creator, request)
