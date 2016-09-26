#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

STUDENT = 'ichigo'

class TestLessonViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = b'http://janux.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    course_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323'
    assets_url = course_url + '/assets'

    def _do_enroll(self):
        admin_environ = self._make_extra_environ(username=self.default_username)
        enroll_url = '/dataserver2/CourseAdmin/UserCourseEnroll'
        data = {'username':STUDENT, 'ntiid': self.course_ntiid, 'scope':'ForCredit'}
        return self.testapp.post_json(enroll_url, data, status=201, extra_environ=admin_environ)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_application_completion_constraints(self):
        # create and enroll student
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(STUDENT)
        self._do_enroll()

        # get all assets
        admin_environ = self._make_extra_environ(username=self.default_username)
        assets_herf = '%s?accept=application/vnd.nextthought.ntilessonoverview' % self.assets_url
        res = self.testapp.get(assets_herf, extra_environ=admin_environ)
        lesson = res.json_body['Items'][0]['ntiid']  # grab first lesson

        # POST constraint
        publication_constraints_link = '/dataserver2/Objects/' + lesson + '/PublicationConstraints'
        assignment = "tag:nextthought.com,2011-10:OU-NAQ-CS1323_F_2015_Intro_to_Computer_Programming.naq.asg.assignment:iClicker_8_26"
        constraint = {
            "MimeType": "application/vnd.nextthought.lesson.assignmentcompletionconstraint",
            'assignments':[assignment]
        }

        res = self.testapp.post_json(publication_constraints_link, constraint, status=201)
        data = res.json_body
        print(data)
