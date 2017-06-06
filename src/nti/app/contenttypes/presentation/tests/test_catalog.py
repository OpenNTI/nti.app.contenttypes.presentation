#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that
from hamcrest import has_property

from zope import interface

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation.interfaces import IContainedTypeAdapter

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestAdapters(ApplicationLayerTest):

    @WithSharedApplicationMockDS(users=False, testapp=False)
    def test_type_adapters(self):

        class Foo():
            pass

        for iface in ALL_PRESENTATION_ASSETS_INTERFACES:
            obj = Foo()
            interface.alsoProvides(obj, iface)
            adapted = IContainedTypeAdapter(obj, None)
            if adapted is not None:
                assert_that(adapted, has_property('type', is_(iface.__name__)))
