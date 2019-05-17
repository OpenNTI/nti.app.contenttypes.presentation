#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import fudge
from hamcrest import not_
from hamcrest import has_key
from hamcrest import assert_that

import unittest

from nti.app.contenttypes.presentation.decorators.outlines import _CourseOutlineNodePublicationConstraintsDecorator

from nti.contenttypes.courses.outlines import CourseOutlineNode

from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraints, INTILessonOverview

from nti.contenttypes.presentation.lesson import NTILessonOverView
from nti.contenttypes.presentation.lesson import AssignmentCompletionConstraint

from nti.externalization.externalization import to_external_object

from nti.app.contenttypes.presentation.decorators.tests import SharedConfiguringTestLayer


class TestDecoration(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def _decorate(self, decorator, context):
        external = to_external_object(context, decorate=False)
        decorator = decorator(context, None)
        decorator.authenticated_userid = 'testuser'
        decorator.decorateExternalMapping(context, external)
        return external

    @fudge.patch('nti.app.contenttypes.presentation.adapters._outlinenode_to_lesson')
    def testPublicationConstraints(self, outlinenode_to_lesson):
        lesson = NTILessonOverView()
        outlinenode_to_lesson.is_callable().returns(lesson)

        context = CourseOutlineNode()

        external = self._decorate(_CourseOutlineNodePublicationConstraintsDecorator, context)
        assert_that(external, not_(has_key('PublicationConstraints')))

        def __conform__(iface):
            if iface == INTILessonOverview:
                return None

        context.__conform__ = __conform__

        external = self._decorate(_CourseOutlineNodePublicationConstraintsDecorator, context)
        assert_that(external, not_(has_key('PublicationConstraints')))

        def __conform__(iface):
            if iface == INTILessonOverview:
                return lesson

        context.__conform__ = __conform__

        assignment_ntiid = u'tag:nextthought.com,2011-10:specific'
        constraint = AssignmentCompletionConstraint(assignments=(assignment_ntiid,))
        ILessonPublicationConstraints(lesson).append(constraint)

        external = self._decorate(_CourseOutlineNodePublicationConstraintsDecorator, context)
        assert_that(external, has_key('PublicationConstraints'))
