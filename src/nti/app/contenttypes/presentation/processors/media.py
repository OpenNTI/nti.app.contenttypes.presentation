#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.processors.mixins import set_creator
from nti.app.contenttypes.presentation.processors.mixins import canonicalize
from nti.app.contenttypes.presentation.processors.mixins import add_to_container
from nti.app.contenttypes.presentation.processors.mixins import get_site_registry
from nti.app.contenttypes.presentation.processors.mixins import get_context_registry

from nti.contenttypes.presentation.interfaces import INTIMediaRoll


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

    __slots__ = ()

    def handle(self, item, context, creator=None, request=None):
        registry = get_context_registry(context)
        return handle_media_roll(item, context, creator, registry)
