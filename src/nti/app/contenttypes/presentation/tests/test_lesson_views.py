#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division

from nti.contenttypes.completion.completion import CompletedItem
from nti.contenttypes.completion.interfaces import ICompletionContext, IPrincipalCompletedItemContainer
from nti.contenttypes.courses.interfaces import ICourseInstance
from zope import component
from zope.security.interfaces import IPrincipal

__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from datetime import datetime

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that

import fudge

from nti.app.contenttypes.presentation.tests.test_models import MockCompletableItem

from nti.dataserver.users.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

STUDENT = u'ichigo'


class TestLessonViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    course_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323'
    assets_url = course_url + '/assets'

    assignment = u"tag:nextthought.com,2011-10:OU-NAQ-CS1323_F_2015_Intro_to_Computer_Programming.naq.asg.assignment:iClicker_8_26"

    survey = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.survey:KNOWING_aristotle"

    def _do_enroll(self):
        enroll_url = '/dataserver2/CourseAdmin/UserCourseEnroll'
        data = {
            'username': STUDENT,
            'ntiid': self.course_ntiid,
            'scope': 'ForCredit'
        }
        return self.testapp.post_json(enroll_url,
                                      data,
                                      status=201)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_assignment_completion_constraints(self):

        # create and enroll student
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(STUDENT)
        self._do_enroll()

        # get all assets
        assets_herf = '%s?accept=application/vnd.nextthought.ntilessonoverview' % self.assets_url
        res = self.testapp.get(assets_herf, status=200)

        # grab first lesson and force-publish
        lesson = res.json_body['Items'][0]['ntiid']
        lesson_link = '/dataserver2/Objects/' + lesson
        self.testapp.post(lesson_link + '/@@publish')
        res = self.testapp.get(lesson_link, status=200)
        self.require_link_href_with_rel(res.json_body, "constraints")

        # POST constraint
        publication_constraints_link = '%s/PublicationConstraints' % lesson_link
        constraint = {
            "MimeType": "application/vnd.nextthought.lesson.assignmentcompletionconstraint",
            'assignments': [self.assignment]
        }

        res = self.testapp.post_json(publication_constraints_link,
                                     constraint, status=201)
        assert_that(res.json_body, has_entry('OID', is_not(none())))
        assert_that(res.json_body, has_entry('NTIID', is_not(none())))
        ntiid = res.json_body['NTIID']

        res = self.testapp.get(publication_constraints_link, status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

        with mock_dataserver.mock_db_trans(self.ds, 'platform.ou.edu'):
            lesson_object = find_object_with_ntiid(lesson)

            student = User.get_user(STUDENT)
            result = lesson_object.is_published(principal=student)
            assert_that(result, is_(False))

            completable1 = MockCompletableItem(self.assignment)

            user_principal = IPrincipal(STUDENT)
            user_completion_container = component.queryMultiAdapter(
                (user_principal, ICompletionContext(ICourseInstance(lesson_object))),
                IPrincipalCompletedItemContainer)

            now = datetime.utcnow()
            completed_item1 = CompletedItem(Principal=user_principal,
                                            Item=completable1,
                                            CompletedDate=now)
            user_completion_container.add_completed_item(completed_item1)

            result = lesson_object.is_published(principal=student)
            assert_that(result, is_(True))

        constraint_link = '/dataserver2/Objects/' + ntiid
        self.testapp.delete(constraint_link, status=204)

        res = self.testapp.get(publication_constraints_link, status=200)
        assert_that(res.json_body, has_entry('Items', has_length(0)))

        clear_constraints_link = '%s/@@clear' % publication_constraints_link
        self.testapp.post_json(clear_constraints_link, status=200)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.contenttypes.presentation.constraints.SurveyCompletionConstraintChecker.check_time_constraint_item')
    def test_survey_completion_constraints(self, check_time_constraint_survey):

        # create and enroll student
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(STUDENT)
        self._do_enroll()

        # get all assets
        assets_herf = '%s?accept=application/vnd.nextthought.ntilessonoverview' % self.assets_url
        res = self.testapp.get(assets_herf, status=200)

        # grab first lesson and force-publish
        lesson = res.json_body['Items'][0]['ntiid']

        lesson_link = '/dataserver2/Objects/' + lesson
        self.testapp.post(lesson_link + '/@@publish')
        res = self.testapp.get(lesson_link, status=200)
        self.require_link_href_with_rel(res.json_body, "constraints")

        # POST constraint
        publication_constraints_link = '%s/PublicationConstraints' % lesson_link
        constraint = {
            "MimeType": "application/vnd.nextthought.lesson.surveycompletionconstraint",
            'surveys': [self.survey]
        }

        res = self.testapp.post_json(publication_constraints_link,
                                     constraint,
                                     status=201)
        assert_that(res.json_body, has_entry('OID', is_not(none())))
        assert_that(res.json_body, has_entry('NTIID', is_not(none())))
        ntiid = res.json_body['NTIID']

        res = self.testapp.get(publication_constraints_link, status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

        with mock_dataserver.mock_db_trans(self.ds, 'platform.ou.edu'):
            lesson_object = find_object_with_ntiid(lesson)

            student = User.get_user(STUDENT)

            check_time_constraint_survey.is_callable().returns(123456789)
            result = lesson_object.is_published(principal=student)
            assert_that(result, is_(True))

            check_time_constraint_survey.is_callable().returns(None)
            result = lesson_object.is_published(principal=student)
            assert_that(result, is_(False))

        constraint_link = '/dataserver2/Objects/' + ntiid
        self.testapp.delete(constraint_link, status=204)

        res = self.testapp.get(publication_constraints_link, status=200)
        assert_that(res.json_body, has_entry('Items', has_length(0)))

        clear_constraints_link = '%s/@@clear' % publication_constraints_link
        self.testapp.post_json(clear_constraints_link, status=200)
