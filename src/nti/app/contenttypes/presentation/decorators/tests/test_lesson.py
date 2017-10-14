#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property

from nti.testing.matchers import validly_provides

import os
import copy
import unittest
import simplejson

from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.contenttypes.presentation.lesson import NTICourseOverViewSpacer

from nti.contenttypes.presentation.utils import prepare_json_text
from nti.contenttypes.presentation.utils import create_object_from_external
from nti.contenttypes.presentation.utils import create_ntilessonoverview_from_external

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.app.contenttypes.presentation.decorators.tests import SharedConfiguringTestLayer


ITEMS = StandardExternalFields.ITEMS


class TestLesson(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_property(self):
        s = NTICourseOverViewSpacer()
        ntiid = s.ntiid
        assert_that(ntiid, is_not(none()))
        assert_that(s, has_property('ntiid', is_(ntiid)))
        assert_that(s.ntiid, is_(ntiid))

    def test_nticourseoverviewspacer(self):
        path = os.path.join(os.path.dirname(__file__), 'nticourseoverviewspacer.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
            original = copy.deepcopy(source)

        spacer = create_object_from_external(source)
        assert_that(spacer, has_property('ntiid', is_not(none())))
        assert_that(spacer, 
					has_property('mimeType', is_("application/vnd.nextthought.nticourseoverviewspacer")))

        ext_obj = to_external_object(spacer)
        for k, v in original.items():
            assert_that(ext_obj, has_entry(k, is_(v)))

    def test_ntilessonoverview(self):
        path = os.path.join(os.path.dirname(__file__), 'ntilessonoverview.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))

        lesson = create_ntilessonoverview_from_external(source)
        assert_that(lesson, 
					has_property('ntiid', is_('tag:nextthought.com,2011-10:OU-NTILessonOverview-LSTD1153_S_2015_History_United_States_1865_to_Present.lec:11.06_LESSON')))
        assert_that(lesson, 
					has_property('lesson', is_('tag:nextthought.com,2011-10:OU-HTML-LSTD1153_S_2015_History_United_States_1865_to_Present.lec:11.06_LESSON')))
        assert_that(lesson, has_property('Items', has_length(5)))
        assert_that(lesson, 
					has_property('mimeType', is_("application/vnd.nextthought.ntilessonoverview")))

        assert_that(lesson, has_length(5))
        assert_that(list(lesson), has_length(5))
        for item in lesson:
            assert_that(item, validly_provides(INTICourseOverviewGroup))

        for item in lesson[1]:
            assert_that(item, validly_provides(INTIAssignmentRef))

        for item in lesson[3]:
            assert_that(item, validly_provides(INTIVideoRef))

        assert_that(lesson[4], has_length(0))

        ext_obj = to_external_object(lesson)
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, 
					has_entry('NTIID', is_("tag:nextthought.com,2011-10:OU-NTILessonOverview-LSTD1153_S_2015_History_United_States_1865_to_Present.lec:11.06_LESSON")))
        assert_that(ext_obj, 
					has_entry('MimeType', is_("application/vnd.nextthought.ntilessonoverview")))
        assert_that(ext_obj, 
					has_entry('title', is_("11.6 Apply Your Knowledge")))
        assert_that(ext_obj, has_entry('Items', has_length(5)))

        assert_that(lesson.remove(lesson.Items[0]), is_(True))
        assert_that(lesson, has_length(4))

    def test_ntilessonoverview_exporter(self):
        path = os.path.join(os.path.dirname(__file__), 'ntilessonoverview.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))

        lesson = create_ntilessonoverview_from_external(source)
        ext_obj = to_external_object(lesson, name="exporter")
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, 
					has_entry('NTIID', is_("tag:nextthought.com,2011-10:OU-NTILessonOverview-LSTD1153_S_2015_History_United_States_1865_to_Present.lec:11.06_LESSON")))
        assert_that(ext_obj, 
					has_entry('MimeType', is_("application/vnd.nextthought.ntilessonoverview")))
        assert_that(ext_obj, 
					has_entry('title', is_("11.6 Apply Your Knowledge")))
        assert_that(ext_obj, has_entry('Items', has_length(5)))
