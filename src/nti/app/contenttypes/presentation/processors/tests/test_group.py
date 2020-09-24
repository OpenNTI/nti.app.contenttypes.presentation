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
from hamcrest import starts_with
from hamcrest import has_properties

import fudge

from zope import component

from pyramid.testing import DummyRequest

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.assessment import NTIAssignmentRef
from nti.contenttypes.presentation.assessment import NTISurveyRef

from nti.contenttypes.presentation.discussion import NTIDiscussionRef

from nti.contenttypes.presentation.group import NTICourseOverViewGroup

from nti.contenttypes.presentation.relatedwork import NTIRelatedWorkRefPointer

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestGroup(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @classmethod
    def course_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(users=True, testapp=False)
    @fudge.patch("nti.app.contenttypes.presentation.processors.group.get_remote_user")
    def test_handle_group(self, mock_grm):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            user = self._get_user(self.default_username)
            mock_grm.is_callable().with_args().returns(user)

            course = ICourseInstance(self.course_entry())
            group = NTICourseOverViewGroup()

            asg_ref = NTIAssignmentRef()
            asg_ref.target = u"tag:nextthought.com,2011-10:OU-NAQ-CS1323_F_2015_Intro_to_Computer_Programming.naq.asg.assignment:iClicker_8_26"
            group.append(asg_ref)

            discussion_id = u"nti-course-bundle://Discussions/Project_10_Help.json"
            dis_ref = NTIDiscussionRef()
            dis_ref.target = discussion_id
            group.append(dis_ref)

            pointer = NTIRelatedWorkRefPointer()
            pointer.target = u'tag:nextthought.com,2011-10:OU-RelatedWorkRef-CS1323_F_2015_Intro_to_Computer_Programming.relatedworkref.relwk:03.01.04_gui_input_tools'
            group.append(pointer)

            request = DummyRequest()
            processor = IPresentationAssetProcessor(group)
            processor.handle(group, course, "ichigo", request)

            assert_that(group,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(course)))

            assert_that(asg_ref,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(group),
                                       'containerId', is_(not_none())))

            assert_that(dis_ref,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(group),
                                       'id', is_(discussion_id),
                                       "target", starts_with('tag:nextthought.com,2011-10')))

            assert_that(pointer,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(group)))

            container = IPresentationAssetContainer(course)
            assert_that(container,
                        has_entry(group.ntiid, is_(group)))
            assert_that(container,
                        has_entry(asg_ref.ntiid, is_(asg_ref)))
            assert_that(container,
                        has_entry(dis_ref.ntiid, is_(dis_ref)))
            assert_that(container,
                        has_entry(pointer.ntiid, is_(pointer)))

            reg = component.queryUtility(IPresentationAsset, asg_ref.ntiid)
            assert_that(reg, is_(asg_ref))

            reg = component.queryUtility(IPresentationAsset, dis_ref.ntiid)
            assert_that(reg, is_(dis_ref))

            reg = component.queryUtility(IPresentationAsset, pointer.ntiid)
            assert_that(reg, is_(pointer))


class TestGroupWithSurveys(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    @classmethod
    def course_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(users=True, testapp=False)
    @fudge.patch("nti.app.contenttypes.presentation.processors.group.get_remote_user")
    def test_handle_group(self, mock_grm):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            user = self._get_user(self.default_username)
            mock_grm.is_callable().with_args().returns(user)

            course = ICourseInstance(self.course_entry())
            group = NTICourseOverViewGroup()

            survey_ref = NTISurveyRef()
            survey_ref.target = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.survey:KNOWING_aristotle"
            survey = find_object_with_ntiid(survey_ref.target)
            survey.title = u"Kurosaki, Inc."
            group.append(survey_ref)

            survey_two_ref = NTISurveyRef()
            survey_two_ref.target = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.survey:KNOWING_aristotle"
            survey_two_ref.title = u"Bleach"
            survey_two_ref.label = u"Just Bleach"
            survey = find_object_with_ntiid(survey_two_ref.target)
            survey.title = u"Kurosaki, Inc."
            group.append(survey_two_ref)

            request = DummyRequest()
            processor = IPresentationAssetProcessor(group)
            processor.handle(group, course, "ichigo", request)

            assert_that(group,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(course)))

            assert_that(survey_ref,
                        has_properties('creator', "ichigo",
                                       'title', u"Kurosaki, Inc.",
                                       'label', u"Kurosaki, Inc.",
                                       "__parent__", is_(group),
                                       'containerId', is_(not_none())))

            assert_that(survey_two_ref,
                        has_properties('creator', "ichigo",
                                       'title', u"Bleach",
                                       'label', u"Just Bleach",
                                       "__parent__", is_(group),
                                       'containerId', is_(not_none())))

            container = IPresentationAssetContainer(course)
            assert_that(container,
                        has_entry(group.ntiid, is_(group)))
            assert_that(container,
                        has_entry(survey_ref.ntiid, is_(survey_ref)))

            reg = component.queryUtility(IPresentationAsset, survey_ref.ntiid)
            assert_that(reg, is_(survey_ref))
