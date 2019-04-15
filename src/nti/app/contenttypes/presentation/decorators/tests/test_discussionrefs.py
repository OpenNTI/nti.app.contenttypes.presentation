#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
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
from nti.contenttypes.presentation.utils import create_discussionref_from_external

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.app.contenttypes.presentation.decorators.tests import SharedConfiguringTestLayer

NTIID = StandardExternalFields.NTIID
CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE


class TestDiscussionRefs(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_discussionref(self):
        path = os.path.join(os.path.dirname(__file__), 'discussionref.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
            original = copy.deepcopy(source)

        discussion = create_discussionref_from_external(source)
        assert_that(discussion, has_property('label', is_('')))
        assert_that(discussion, has_property('ntiid', is_(not_none())))
        assert_that(discussion, has_property('id', is_(discussion.ntiid)))
        assert_that(discussion,
                    has_property('title', is_('11.6 Perspectives')))
        assert_that(discussion,
                    has_property('icon', is_("resources/LSTD1153_S_2015_History_United_States_1865_to_Present/8c9c6e901a7884087d71ccf46941ad258121abce/fd35e23767020999111e1f49239199b4c5eff23e.jpg")))
        assert_that(discussion,
                    has_property('mimeType', is_("application/vnd.nextthought.discussionref")))
        assert_that(discussion,
                    has_property('target', is_("tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseRoot-Open_Discussions.11_6_Perspectives")))

        ext_obj = to_external_object(discussion)
        for k, v in original.items():
            if k not in (MIMETYPE, CLASS, NTIID):
                assert_that(ext_obj, has_entry(k, is_(v)))

        assert_that(ext_obj, has_key('MimeType'))
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, has_key('NTIID'))

    def test_discussionref_bundle(self):
        path = os.path.join(os.path.dirname(__file__),
                            'discussionref_bundle.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))

        discussion = create_discussionref_from_external(source)
        assert_that(discussion, has_property('label', is_('Ichigo')))
        assert_that(discussion, has_property('title', is_('Ichigo')))
        assert_that(discussion, has_property('ntiid', is_(not_none())))
        assert_that(discussion,
                    has_property('icon', is_("resources/ichigo.jpg")))
        assert_that(discussion,
                    has_property('mimeType', is_("application/vnd.nextthought.discussionref")))
        assert_that(discussion,
                    has_property('id', is_("nti-course-bundle://Discussions/ichigo.json")))
        assert_that(discussion,
                    has_property('target', is_("nti-course-bundle://Discussions/ichigo.json")))
