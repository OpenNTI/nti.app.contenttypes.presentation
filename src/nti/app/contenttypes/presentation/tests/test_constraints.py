#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods
from datetime import datetime

import fudge

from hamcrest import none, is_
from hamcrest import is_not
from hamcrest import assert_that

import unittest

from ZODB.interfaces import IConnection

from zope.security.interfaces import IPrincipal

from nti.contenttypes.completion.adapters import CompletedItemContainer

from nti.contenttypes.completion.completion import CompletedItem
from nti.contenttypes.completion.completion import PrincipalCompletedItemContainer

from nti.app.metadata.tests import SharedConfiguringTestLayer

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User

from ..constraints import AssignmentCompletionConstraintChecker

from .test_models import MockCompletableItem

STUDENT = u'ichigo'


class TestAssignmentCompletionConstraintChecker(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    assignment = u"tag:nextthought.com,2011-10:OU-NAQ-CS1323_F_2015_Intro_to_CS.naq.asg.assignment:iClicker_8_26"

    def _user_completion_container(self, principal):
        user_completion_container = PrincipalCompletedItemContainer(principal)
        IConnection(self.ds.root).add(user_completion_container)
        return user_completion_container

    def _completion_container(self, username=None, completed_items=None):
        completion_container = CompletedItemContainer()
        if username:
            user_principal = IPrincipal(username)
            user_completion_container = self._user_completion_container(user_principal)
            completion_container[username] = user_completion_container
            for item in completed_items or ():
                user_completion_container.add_completed_item(item)

        return completion_container

    @staticmethod
    def _completed_item(username, completable, date=None):
        kwargs = {}
        if date is not None:
            kwargs['CompletedDate'] = date
        return CompletedItem(Principal=IPrincipal(username),
                             Item=completable,
                             **kwargs)

    def _test_check_time_constraint_item(self):
        checker = AssignmentCompletionConstraintChecker()
        student = User.create_user(username=STUDENT)

        constraint = fudge.Fake('AssignmentCompletionConstraint')

        return checker.check_time_constraint_item(self.assignment, student, constraint=constraint)

    @WithMockDSTrans
    @fudge.patch('nti.app.contenttypes.presentation.constraints.AssignmentCompletionConstraintChecker._completed_items')
    def test_check_time_constraint_item_no_container(self, completed_items):
        completed_items.is_callable().returns(None)

        completed_time = self._test_check_time_constraint_item()

        assert_that(completed_time, is_(none()))

    @WithMockDSTrans
    @fudge.patch('nti.app.contenttypes.presentation.constraints.AssignmentCompletionConstraintChecker._completed_items')
    def test_check_time_constraint_item_no_user_container(self, completed_items):
        completion_container = self._completion_container()
        completed_items.is_callable().returns(completion_container)

        completed_time = self._test_check_time_constraint_item()

        assert_that(completed_time, is_(none()))

    @WithMockDSTrans
    @fudge.patch('nti.app.contenttypes.presentation.constraints.AssignmentCompletionConstraintChecker._completed_items')
    def test_check_time_constraint_item_empty_user_container(self, completed_items):
        completion_container = self._completion_container(STUDENT, completed_items=())
        completed_items.is_callable().returns(completion_container)

        completed_time = self._test_check_time_constraint_item()

        assert_that(completed_time, is_(none()))

    @WithMockDSTrans
    @fudge.patch('nti.app.contenttypes.presentation.constraints.AssignmentCompletionConstraintChecker._completed_items')
    def test_check_time_constraint_item_no_date(self, completed_items):
        completed_item = self._completed_item(STUDENT, MockCompletableItem(self.assignment))
        completion_container = self._completion_container(STUDENT, completed_items=(completed_item,))
        completed_items.is_callable().returns(completion_container)

        completed_time = self._test_check_time_constraint_item()

        assert_that(completed_time, is_(none()))

    @WithMockDSTrans
    @fudge.patch('nti.app.contenttypes.presentation.constraints.AssignmentCompletionConstraintChecker._completed_items')
    def test_check_time_constraint_item_success(self, completed_items):
        completed_item = self._completed_item(STUDENT, MockCompletableItem(self.assignment), date=datetime.utcnow())
        completion_container = self._completion_container(STUDENT, completed_items=(completed_item,))
        completed_items.is_callable().returns(completion_container)

        completed_time = self._test_check_time_constraint_item()

        assert_that(completed_time, is_not(none()))

