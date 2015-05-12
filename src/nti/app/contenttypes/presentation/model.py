#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.annotation.interfaces import IAnnotations

from nti.dataserver.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from .interfaces import IPresentationAssetContainter

@interface.implementer(IPresentationAssetContainter)
class PresentationAssetContainter(CaseInsensitiveCheckingLastModifiedBTreeContainer):
	pass

@interface.implementer(IPresentationAssetContainter)
def _presentation_asset_container_factory(context, create=True):
	result = None
	annotations = IAnnotations(context)
	try:
		KEY = 'PresentationAssetContainter'
		result = annotations[KEY]
	except KeyError:
		if create:
			result = PresentationAssetContainter()
			annotations[KEY] = result
			result.__name__ = KEY
			result.__parent__ = context
	return result
