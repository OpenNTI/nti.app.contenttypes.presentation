#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import interface

from zope.container.interfaces import IContainer

from zope.container.constraints import contains

from nti.contenttypes.presentation.interfaces import IPresentationAsset

class IPresentationAssetContainter(IContainer):
    contains(IPresentationAsset)
    
class IPresentationAssetsIndex(interface.Interface):
    
    def reset():
        pass

class IItemRefValidator(interface.Interface):
    
    def validate():
        pass
