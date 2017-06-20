#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_properties

from zope import component

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.slide import NTISlide
from nti.contenttypes.presentation.slide import NTISlideDeck
from nti.contenttypes.presentation.slide import NTISlideVideo

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestPackage(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @classmethod
    def course_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(users=False, testapp=False)
    def test_handle_docket(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            course = ICourseInstance(self.course_entry())

            deck = NTISlideDeck()
            deck.ntiid = u'tag:nextthought.com,2011-10:OU-NTISlideDeck-Install_Mac'
            
            slide = NTISlide()
            slide.slidevideoid = u'tag:nextthought.com,2011-10:OU-NTISlideVideo-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Install_Mac_video'
            deck.append(slide)
            
            video = NTISlideVideo()
            video.video = u'tag:nextthought.com,2011-10:OU-NTISlideVideo-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Install_Mac_video'
            deck.append(video)

            processor = IPresentationAssetProcessor(deck)
            processor.handle(deck, course, "ichigo")

            assert_that(deck,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(course)))
            
            assert_that(slide,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(deck)))
            
            assert_that(video,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(deck)))
            container = IPresentationAssetContainer(course)
            assert_that(container,
                        has_entry(deck.ntiid, is_(deck)))
            assert_that(container,
                        has_entry(slide.ntiid, is_(slide)))
            assert_that(container,
                        has_entry(video.ntiid, is_(video)))
            
            reg = component.queryUtility(INTISlide, slide.ntiid)
            assert_that(reg, is_(slide))
            
            reg = component.queryUtility(INTISlideVideo, video.ntiid)
            assert_that(reg, is_(video))
