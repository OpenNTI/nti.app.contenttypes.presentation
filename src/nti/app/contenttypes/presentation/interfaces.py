#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import interface

from zc.catalog.interfaces import IValueIndex

class IParentIndex(IValueIndex):
    pass

class IItemRefValidator(interface.Interface):
    
    def validate():
        pass
