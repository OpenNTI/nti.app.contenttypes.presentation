#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 1

from zope import interface

from zope.generations.interfaces import IInstallableSchemaManager
from zope.generations.generations import SchemaManager as BaseSchemaManager

from ..index import install_parent_index

@interface.implementer(IInstallableSchemaManager)
class _SchemaManager(BaseSchemaManager):
    """
    A schema manager that we can register as a utility in ZCML.
    """
    def __init__( self ):
        super(_SchemaManager, self).__init__(
            generation=generation,
            minimum_generation=generation,
            package_name='nti.app.contenttypes.presentation.generations')

    def install( self, context ):
        pass

def evolve(context):
    install_parent_index(context)
