#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from persistent import Persistent

from zope.component.persistentregistry import PersistentComponents as Components

from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin

import zope.testing.cleanup


class SharedConfiguringTestLayer(ZopeComponentLayer,
                                 ConfiguringLayerMixin):

    set_up_packages = ('nti.app.contenttypes.presentation',)

    @classmethod
    def setUp(cls):
        cls.setUpPackages()

    @classmethod
    def tearDown(cls):
        cls.tearDownPackages()
        zope.testing.cleanup.cleanUp()

    @classmethod
    def testSetUp(cls):
        pass

    @classmethod
    def testTearDown(cls):
        pass


import unittest


class ContentTypesMediaLayerTest(unittest.TestCase):
    layer = SharedConfiguringTestLayer


INVALID_TITLE_LENGTH = 301


class PersistentComponents(Components, Persistent):
    pass
