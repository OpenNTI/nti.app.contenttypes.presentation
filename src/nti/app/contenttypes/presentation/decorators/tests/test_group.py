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
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

import os
import copy
import unittest
import simplejson

from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.contenttypes.presentation.group import NTICourseOverViewGroup

from nti.contenttypes.presentation.utils import prepare_json_text
from nti.contenttypes.presentation.utils import create_nticourseoverviewgroup_from_external

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from nti.app.contenttypes.presentation.decorators.tests import SharedConfiguringTestLayer

ITEMS = StandardExternalFields.ITEMS


class TestGroup(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_property(self):
        group = NTICourseOverViewGroup()
        ntiid = group.ntiid
        assert_that(ntiid, is_not(none()))
        assert_that(group, has_property('ntiid', is_(ntiid)))
        assert_that(group.ntiid, is_(ntiid))

    def test_nticourseoverviewgroup(self):
        path = os.path.join(os.path.dirname(__file__), 'nticourseoverviewgroup.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
            original = copy.deepcopy(source)

        group = create_nticourseoverviewgroup_from_external(source)
        assert_that(group, has_property('ntiid', is_not(none())))
        assert_that(group, has_property('color', is_('f11824e')))
        assert_that(group, has_property('title', is_('Required Resources')))
        assert_that(group, has_property('Items', has_length(5)))
        assert_that(group, 
					has_property('mimeType', is_("application/vnd.nextthought.nticourseoverviewgroup")))

        assert_that(group, has_length(5))
        assert_that(list(group), has_length(5))
        assert_that(group[0], validly_provides(INTIRelatedWorkRef))
        assert_that(group[1], verifiably_provides(INTIDiscussionRef))
        assert_that(group[2], verifiably_provides(INTIDiscussionRef))
        assert_that(group[3], verifiably_provides(INTIAssignmentRef))
        assert_that(group[4], verifiably_provides(INTIVideoRef))

        assert_that(group[1], has_property('ntiid', is_(not_none())))
        assert_that(group[1], 
					has_property('target', is_('tag:nextthought.com,2011-10:AGEC_4990-Topic:EnrolledCourseSection-In_Class_Discussions.Introduce_Yourself')))

        assert_that(group[2], has_property('ntiid', is_(not_none())))
        assert_that(group[2], 
					has_property('target', is_('tag:nextthought.com,2011-10:AGEC_4990-Topic:EnrolledCourseSection-Open_Discussions.Introduce_Yourself')))

        ext_obj = to_external_object(group)
        for k, v in original.items():
            if k != ITEMS:
                assert_that(ext_obj, has_entry(k, is_(v)))

        assert_that(ext_obj, has_key('MimeType'))
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, has_key('NTIID'))

        ext_obj = to_external_object(group)
        assert_that(ext_obj, has_entry(ITEMS, has_length(5)))
        factory = find_factory_for(ext_obj)
        new_object = factory()
        update_from_external_object(new_object, ext_obj)
        assert_that(new_object, has_length(5))

        assert_that(group.remove(group.Items[0]), is_(True))
        assert_that(group, has_length(4))
