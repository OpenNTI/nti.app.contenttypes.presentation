#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_property

import os
import copy
import unittest
import simplejson

from nti.contenttypes.presentation.utils import prepare_json_text
from nti.contenttypes.presentation.utils import create_timelime_from_external

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.externalization import to_external_object

from nti.app.contenttypes.presentation.decorators.tests import SharedConfiguringTestLayer

MIMETYPE = StandardExternalFields.MIMETYPE

class TestTimeline(unittest.TestCase):

	layer = SharedConfiguringTestLayer

	def test_timeline(self):
		path = os.path.join(os.path.dirname(__file__), 'timeline.json')
		with open(path, "r") as fp:
			source = simplejson.loads(prepare_json_text(fp.read()))
			original = copy.deepcopy(source)

		timeline = create_timelime_from_external(source)
		assert_that(timeline, has_property('label', is_(u"Heading West")))
		assert_that(timeline, has_property('mimeType', is_(u"application/vnd.nextthought.ntitimeline")))
		assert_that(timeline, has_property('description', is_(u"An overview of key dates and events")))
		assert_that(timeline, has_property('ntiid', is_(u"tag:nextthought.com,2011-10:OU-JSON:Timeline-LSTD1153_S_2015_History_United_States_1865_to_Present.timeline.heading_west")))
		assert_that(timeline, has_property('href', is_(u"resources/LSTD1153_S_2015_History_United_States_1865_to_Present/d1b15ecbe7e15f47d1927624e23b40509d37f135/90784fa2c5c148922446e05d45ff35f0aee3e69b.json")))
		assert_that(timeline, has_property('icon', is_(u"resources/LSTD1153_S_2015_History_United_States_1865_to_Present/75d1ec44cd623dfdc373b705523e05259f61c821/fd35e23767020999111e1f49239199b4c5eff23e.jpg")))

		ext_obj = to_external_object(timeline)
		for k, v in original.items():
			if k == 'ntiid':
				k = 'NTIID'
			if k != MIMETYPE:
				assert_that(ext_obj, has_entry(k, is_(v)))

		assert_that(ext_obj, has_key('MimeType'))
		assert_that(ext_obj, has_key('Class'))
		assert_that(ext_obj, has_key('NTIID'))

	def test_ntitimeline(self):
		path = os.path.join(os.path.dirname(__file__), 'ntitimeline.json')
		with open(path, "r") as fp:
			source = simplejson.loads(prepare_json_text(fp.read()))

		assert_that(source, has_entry(MIMETYPE, is_('application/vnd.nextthought.ntitimeline')))

		timeline = create_timelime_from_external(source)
		assert_that(timeline, has_property('label', is_(u"Reconstruction and The New South")))
		assert_that(timeline, has_property('mimeType', is_(u"application/vnd.nextthought.ntitimeline")))
		assert_that(timeline, has_property('description', is_(u"An overview of key dates and events")))
		assert_that(timeline, has_property('ntiid', is_(u"tag:nextthought.com,2011-10:OU-JSON:Timeline-LSTD1153_S_2015_History_United_States_1865_to_Present.timeline.reconstruction_and_the_new_south")))
		assert_that(timeline, has_property('href', is_(u"resources/LSTD1153_S_2015_History_United_States_1865_to_Present/78ce0e2995d1fee5d2be8caf1b98ce56698a56dd/90784fa2c5c148922446e05d45ff35f0aee3e69b.json")))
		assert_that(timeline, has_property('icon', is_(u"resources/LSTD1153_S_2015_History_United_States_1865_to_Present/b6aae2745b753ec75302c7e95e329983b43fb606/fd35e23767020999111e1f49239199b4c5eff23e.jpg")))

		ext_obj = to_external_object(timeline)
		assert_that(ext_obj, has_entry('suggested-inline', is_(False)))
		assert_that(ext_obj, has_entry('label', is_('Reconstruction and The New South')))
		assert_that(ext_obj, has_entry('desc', is_('An overview of key dates and events')))
		assert_that(ext_obj, has_entry('NTIID', is_not(none())))
		assert_that(ext_obj, has_entry('label', is_not(none())))
		assert_that(ext_obj, has_entry('href', is_not(none())))
		assert_that(ext_obj, has_entry('MimeType', is_('application/vnd.nextthought.ntitimeline')))
		assert_that(ext_obj, has_key('Class'))
