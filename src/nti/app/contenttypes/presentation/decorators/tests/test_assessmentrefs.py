#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_property

import os
import copy
import unittest
import simplejson

from nti.contenttypes.presentation.utils import prepare_json_text
from nti.contenttypes.presentation.utils import create_surveyref_from_external
from nti.contenttypes.presentation.utils import create_questionref_from_external
from nti.contenttypes.presentation.utils import create_assignmentref_from_external
from nti.contenttypes.presentation.utils import create_questionsetref_from_external

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.app.contenttypes.presentation.decorators.tests import SharedConfiguringTestLayer

CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE


class TestAssignmentRef(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_assignmentref(self):
        path = os.path.join(os.path.dirname(__file__), 'assignmentref.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
            original = copy.deepcopy(source)
        assert_that(source,
                    has_entry(MIMETYPE, is_('application/vnd.nextthought.assessment.assignment')))

        assignment = create_assignmentref_from_external(source)
        assert_that(assignment,
                    has_property('containerId', is_('tag:nextthought.com,2011-10:OU-HTML-LSTD1153_S_2015_History_United_States_1865_to_Present.discussions:_the_liberal_hour')))
        assert_that(assignment,
                    has_property('title', is_('Discussions: The Liberal Hour')))
        assert_that(assignment,
                    has_property('label', is_('Discussions: The Liberal Hour')))
        assert_that(assignment,
                    has_property('target', is_("tag:nextthought.com,2011-10:OU-NAQ-LSTD1153_S_2015_History_United_States_1865_to_Present.naq.asg.assignment:11.6_discussions")))
        assert_that(assignment,
                    has_property('ntiid', is_not("tag:nextthought.com,2011-10:OU-NAQ-LSTD1153_S_2015_History_United_States_1865_to_Present.naq.asg.assignment:11.6_discussions")))

        ext_obj = to_external_object(assignment)
        for k, v in original.items():
            if k not in (MIMETYPE, CLASS, 'NTIID'):
                assert_that(ext_obj, has_entry(k, is_(v)))

        assert_that(ext_obj, has_key('MimeType'))
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, has_key('NTIID'))

    def test_questionsetref(self):
        path = os.path.join(os.path.dirname(__file__), 'questionsetref.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
            original = copy.deepcopy(source)
        assert_that(source,
                    has_entry(MIMETYPE, is_('application/vnd.nextthought.naquestionset')))

        questionset = create_questionsetref_from_external(source)
        assert_that(questionset, has_property('question_count', is_(7)))
        assert_that(questionset, has_property('ntiid', is_(not_none())))
        assert_that(questionset,
                    has_property('label', is_('Janux Course Features Verification Quiz')))
        assert_that(questionset,
                    has_property('target', is_("tag:nextthought.com,2011-10:OU-NAQ-CHEM4970_200_F_2014_Chemistry_of_Beer.naq.set.qset:janux_features_verification_quiz")))

        ext_obj = to_external_object(questionset)
        for k, v in original.items():
            if k not in (MIMETYPE, CLASS):
                assert_that(ext_obj, has_entry(k, is_(v)))

        assert_that(ext_obj, has_key('MimeType'))
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, has_key('NTIID'))

    def test_questionref(self):
        path = os.path.join(os.path.dirname(__file__), 'questionref.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
            original = copy.deepcopy(source)
        assert_that(source,
                    has_entry(MIMETYPE, is_('application/vnd.nextthought.naquestion')))

        question = create_questionref_from_external(source)
        assert_that(question,
                    has_property('target', is_("tag:nextthought.com,2011-10:OKState-NAQ-OKState_AGEC4990_S_2015_Farm_to_Fork.naq.qid.FootprintQuiz.01")))
        assert_that(question, has_property('ntiid', is_(not_none())))

        ext_obj = to_external_object(question)
        for k, v in original.items():
            if k not in (MIMETYPE, CLASS):
                assert_that(ext_obj, has_entry(k, is_(v)))

        assert_that(ext_obj, has_key('MimeType'))
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, has_key('NTIID'))

    def test_surveyref(self):
        path = os.path.join(os.path.dirname(__file__), 'surveyref.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
            original = copy.deepcopy(source)
        assert_that(source,
                    has_entry(MIMETYPE, is_('application/vnd.nextthought.nasurvey')))

        question = create_surveyref_from_external(source)
        assert_that(question,
                    has_property('target', is_("tag:nextthought.com,2011-10:NTIAlpha-NAQ-NTI1000_TestCourse.naq.survey.survey_test")))
        assert_that(question,
                    has_property('ntiid', is_not("tag:nextthought.com,2011-10:NTIAlpha-NAQ-NTI1000_TestCourse.naq.survey.survey_test")))

        ext_obj = to_external_object(question)
        for k, v in original.items():
            if k not in (MIMETYPE, 'NTIID'):
                assert_that(ext_obj, has_entry(k, is_(v)))
            elif k == MIMETYPE:
                assert_that(ext_obj,
                            has_entry(k, is_('application/vnd.nextthought.surveyref')))

        assert_that(ext_obj, has_key('MimeType'))
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, has_key('NTIID'))
