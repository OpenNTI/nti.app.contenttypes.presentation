#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urllib import unquote

from zope import interface

from zope.container.contained import Contained

from zope.traversing.interfaces import IPathAdapter

from pyramid import httpexceptions as hexc

from nti.ntiids.ntiids import find_object_with_ntiid

@interface.implementer(IPathAdapter)
class AssetsPathAdapter(Contained):

    def __init__(self, parent, request):
        self.request = request
        self.__parent__ = parent
        self.__name__ = "assets"

    def __getitem__(self, ntiid):
        if not ntiid:
            raise hexc.HTTPNotFound()
        ntiid = unquote(ntiid)
        result = find_object_with_ntiid(ntiid)
        if result is not None:
            return result
        raise KeyError(ntiid)
