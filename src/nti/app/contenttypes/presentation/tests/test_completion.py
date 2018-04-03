#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_items
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import greater_than_or_equal_to
does_not = is_not

from itertools import chain

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_NOT_REQUIRED_VIEW_NAME

from nti.app.contenttypes.presentation import VIEW_CONTENTS
from nti.app.contenttypes.presentation import VIEW_OVERVIEW_CONTENT

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ICompletableItemProvider
from nti.contenttypes.completion.interfaces import IRequiredCompletableItemProvider
from nti.contenttypes.completion.interfaces import ICompletableItemDefaultRequiredPolicy

from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation import VIDEO_MIME_TYPES

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid


class TestCompletion(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    course_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323'

    reading_ntiid = "tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.reading:rules_etiquette"
    pdf_ntiid = "tag:nextthought.com,2011-10:OU-RelatedWorkRef-CS1323_F_2015_Intro_to_Computer_Programming.relatedworkref.relwk:syllabus"
    video_ntiid = "tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Welcome"

    outline_contents_url = '%s/Outline/%s' % (course_url, VIEW_CONTENTS)

    @Lazy
    def video_lesson_overview_url(self):
        res = self.testapp.get(self.outline_contents_url)
        res = res.json_body
        unit_ext = res[0]
        content_ext = unit_ext['contents'][0]
        lesson_overview_url = self.require_link_href_with_rel(content_ext,
                                                              VIEW_OVERVIEW_CONTENT)
        return lesson_overview_url

    def _get_video_lesson(self):
        return self.testapp.get(self.video_lesson_overview_url).json_body

    @Lazy
    def ref_lesson_overview_url(self):
        res = self.testapp.get(self.outline_contents_url)
        res = res.json_body
        unit_ext = res[1]
        content_ext = unit_ext['contents'][0]
        lesson_overview_url = self.require_link_href_with_rel(content_ext,
                                                              VIEW_OVERVIEW_CONTENT)
        return lesson_overview_url

    def _get_ref_lesson(self):
        return self.testapp.get(self.ref_lesson_overview_url).json_body

    def _set_completion_policy(self):
        aggregate_mimetype = CompletableItemAggregateCompletionPolicy.mime_type
        full_data = {u'MimeType': aggregate_mimetype}
        course_res = self.testapp.get(self.course_url).json_body
        policy_url = self.require_link_href_with_rel(course_res,
                                                     COMPLETION_POLICY_VIEW_NAME)
        return self.testapp.put_json(policy_url, full_data).json_body

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_assets(self):
        """
        Test required state on assets.
        """
        policy_res = self._set_completion_policy()
        res = self._get_video_lesson()
        video_groups = res['Items']
        res = self._get_ref_lesson()
        ref_groups = res['Items']
        for group in chain(video_groups, ref_groups):
            for item in group['Items']:
                if item['Class'] == u'ContentVideoCollection':
                    for item in item['Items']:
                        assert_that(item[u'CompletionDefaultState'], is_(False))
                        assert_that(item[u'IsCompletionDefaultState'], is_(True))
                        assert_that(item[u'CompletionRequired'], is_(False))
                else:
                    assert_that(item[u'CompletionDefaultState'], is_(False))
                    assert_that(item[u'IsCompletionDefaultState'], is_(True))
                    assert_that(item[u'CompletionRequired'], is_(False))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            course = find_object_with_ntiid(self.entry_ntiid)
            course = ICourseInstance(course)
            default_required = ICompletableItemDefaultRequiredPolicy(course)
            assert_that(default_required.mime_types, has_length(0))
            for video_mime in VIDEO_MIME_TYPES:
                default_required.mime_types.add(video_mime)

            user = User.get_user('sjohnson@nextthought.com')
            providers = component.subscribers((course,),
                                              ICompletableItemProvider)
            providers = tuple(providers)
            assert_that(providers, has_length(greater_than_or_equal_to(1)))
            possible_items = set()
            for provider in providers:
                possible_items.update(provider.iter_items(user))
            assert_that(possible_items, has_length(greater_than_or_equal_to(3)))

        # Videos are now default required
        res = self._get_video_lesson()
        video_groups = res['Items']
        res = self._get_ref_lesson()
        ref_groups = res['Items']
        for group in video_groups:
            for item in group['Items']:
                for item in item['Items']:
                    assert_that(item[u'CompletionDefaultState'], is_(True))
                    assert_that(item[u'IsCompletionDefaultState'], is_(True))
                    assert_that(item[u'CompletionRequired'], is_(True))

        for group in ref_groups:
            for item in group['Items']:
                assert_that(item[u'CompletionDefaultState'], is_(False))
                assert_that(item[u'IsCompletionDefaultState'], is_(True))
                assert_that(item[u'CompletionRequired'], is_(False))

        # Video explicitly optional; ref explicitly required
        required_url = self.require_link_href_with_rel(policy_res,
                                                       COMPLETION_REQUIRED_VIEW_NAME)
        not_required_url = self.require_link_href_with_rel(policy_res,
                                                       COMPLETION_NOT_REQUIRED_VIEW_NAME)
        self.testapp.put_json(not_required_url, {u'ntiid': self.video_ntiid})
        self.testapp.put_json(required_url, {u'ntiid': self.pdf_ntiid})
        self.testapp.put_json(required_url, {u'ntiid': self.reading_ntiid})

        res = self._get_video_lesson()
        video_groups = res['Items']
        res = self._get_ref_lesson()
        ref_groups = res['Items']
        for group in video_groups:
            for item in group['Items']:
                for item in item['Items']:
                    if item['NTIID'] == self.video_ntiid:
                        assert_that(item[u'CompletionDefaultState'], is_(True))
                        assert_that(item[u'IsCompletionDefaultState'], is_(False))
                        assert_that(item[u'CompletionRequired'], is_(False))
                    else:
                        assert_that(item[u'CompletionDefaultState'], is_(True))
                        assert_that(item[u'IsCompletionDefaultState'], is_(True))
                        assert_that(item[u'CompletionRequired'], is_(True))

        for group in ref_groups:
            for item in group['Items']:
                if     item['NTIID'] == self.pdf_ntiid \
                    or item['target-NTIID'] == self.reading_ntiid:
                    assert_that(item[u'CompletionDefaultState'], is_(False))
                    assert_that(item[u'IsCompletionDefaultState'], is_(False))
                    assert_that(item[u'CompletionRequired'], is_(True))
                else:
                    assert_that(item[u'CompletionDefaultState'], is_(False))
                    assert_that(item[u'IsCompletionDefaultState'], is_(True))
                    assert_that(item[u'CompletionRequired'], is_(False))

        # Completable item provider
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            user = User.get_user('sjohnson@nextthought.com')
            course = find_object_with_ntiid(self.entry_ntiid)
            course = ICourseInstance(course)
            providers = component.subscribers((course,),
                                              IRequiredCompletableItemProvider)
            providers = tuple(providers)
            assert_that(providers, has_length(greater_than_or_equal_to(1)))
            items = set()
            for provider in providers:
                items.update(provider.iter_items(user))
            assert_that(items, has_length(greater_than_or_equal_to(3)))
            assert_that(items, has_items(has_property('ntiid', self.reading_ntiid),
                                         has_property('ntiid', self.pdf_ntiid),
                                         has_property('mime_type',
                                                      'application/vnd.nextthought.ntivideo'),
                                         does_not(
                                            has_property('ntiid', self.video_ntiid))))
            progress = component.queryMultiAdapter((user,course), IProgress)
            assert_that(progress.AbsoluteProgress, is_(0))
            assert_that(progress.MaxPossibleProgress, is_(13))
            assert_that(progress.HasProgress, is_(False))
            assert_that(progress.LastModified, none())
