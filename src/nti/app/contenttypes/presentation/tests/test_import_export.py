#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import contains
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

import shutil
import tempfile

from nti.app.contenttypes.presentation.exporter import LessonOverviewsExporter
from nti.app.contenttypes.presentation.importer import LessonOverviewsImporter

from nti.cabinet.filer import DirectoryFiler

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

class TestExporter(ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'
	entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

	@classmethod
	def course_entry(cls):
		return find_object_with_ntiid(cls.entry_ntiid)

	@WithSharedApplicationMockDS(testapp=False, users=True)
	def test_lesson_exporter(self):
		tmp_dir = tempfile.mkdtemp(dir="/tmp")
		try:
			filer = DirectoryFiler(tmp_dir)
			# export
			with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
				course = ICourseInstance(self.course_entry())
				exporter = LessonOverviewsExporter()
				exporter.export(course, filer)
				assert_that(filer.list(), contains('Lessons'))
				assert_that(filer.list("Lessons"), has_length(17))

			# import
			with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
				course = ICourseInstance(self.course_entry())
				importer = LessonOverviewsImporter()
				result = importer.process(course, filer, False)
				assert_that(result, has_length(17))
		finally:
			shutil.rmtree(tmp_dir, True)