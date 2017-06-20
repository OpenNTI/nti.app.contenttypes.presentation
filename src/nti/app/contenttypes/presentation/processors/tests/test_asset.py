#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_property

from zope import interface

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.processors.asset import handle_asset

from nti.contenttypes.courses.courses import CourseInstance 

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.media import NTIVideo

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestAsset(ApplicationLayerTest):

    def test_adapters(self):
        
        class Foo(object):
            pass

        for provided in ALL_PRESENTATION_ASSETS_INTERFACES:
            item = Foo()
            interface.alsoProvides(item, provided)
            processor = IPresentationAssetProcessor(item, None)
            assert_that(processor, is_(not_none()))
            
    @WithSharedApplicationMockDS(users=False, testapp=False)
    def test_handle_asset(self):
        context = CourseInstance()
        video = NTIVideo()
        ntiid = video.ntiid = u'tag:nextthought.com,2011-10:OU-NTIVideo-BLEACH.ntivideo.video_Kurosaki_Ichigo'
        handle_asset(video, context, "ichigo")
        assert_that(video,
                    has_property('creator', "ichigo"))
        container = IPresentationAssetContainer(context)
        assert_that(container,
                    has_entry(ntiid, video))
