#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
# from nti.contenttypes.presentation.lesson import AssignmentCompletionConstraint

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

import os
import simplejson
from nti.contenttypes.presentation.utils import prepare_json_text

STUDENT = 'ichigo'


class TestLessonViews(ApplicationLayerTest):
	
	def _load_resource(self, name):
		path = os.path.join(os.path.dirname(__file__), name)
		with open(path, "r") as fp:
			source = simplejson.loads(prepare_json_text(fp.read()))
		return source
	
	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323_SubInstances_995'
	course_href = '/dataserver2/Objects/%s' % course_ntiid
	
	def _do_enroll(self):
		admin_environ = self._make_extra_environ(username=self.default_username)
		enroll_url = '/dataserver2/CourseAdmin/UserCourseEnroll'
		data = {'username':STUDENT, 'ntiid': self.course_ntiid, 'scope':'ForCredit'}
		return self.testapp.post_json(enroll_url, data, status=201, extra_environ=admin_environ)

	@WithSharedApplicationMockDS(testapp=True, users=(STUDENT,))
	def test_application_completion_constraints(self):
		res = self._do_enroll()
		
		from IPython.core.debugger import Tracer; Tracer()()
		source = self._load_resource('ntilessonoverview.json')
		ntiid = source.pop('NTIID', None)

		# request media by outline
		course_ext = res.json_body['CourseInstance']
		course_href = course_ext.get( 'href' )
		ichigo_environ = self._make_extra_environ(username=STUDENT)
		res = self.testapp.get( course_href, extra_environ=ichigo_environ )
		course_ext = res.json_body
		
# 		lesson_overview = 'tag:nextthought.com,2011-10:NTI-NTILessonOverview-Fall2015_CS_1323_0_tryt3968_4743973034483803302_0'

		lesson = 'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.01_LESSON'
		children = [ "tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Welcome",
					 "tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Code",
					 "tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Obama",
					 "tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Java",
					 "tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Academic_Integrity"]

		publication_constraints_link = '/dataserver2/objects/' + ntiid + '/PublicationConstraints'
		
		constraint = {"MimeType": "application/vnd.nextthought.lesson.assignmentcompletionconstraint", 
					'assignments':["tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Welcome"]}

		res = self.testapp.post(publication_constraints_link, constraint)
# 		data = res.json_body

		
