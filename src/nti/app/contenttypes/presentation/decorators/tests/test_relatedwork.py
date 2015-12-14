#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_property

import os
import copy
import unittest
import simplejson

from nti.contenttypes.presentation.utils import prepare_json_text
from nti.contenttypes.presentation.utils import create_object_from_external

from nti.externalization.externalization import to_external_object

from nti.app.contenttypes.presentation.decorators.tests import SharedConfiguringTestLayer

class TestRelatedWork(unittest.TestCase):

	layer = SharedConfiguringTestLayer

	def test_related(self):
		path = os.path.join(os.path.dirname(__file__), 'relatedwork.json')
		with open(path, "r") as fp:
			source = simplejson.loads(prepare_json_text(fp.read()))
			original = copy.deepcopy(source)

		related = create_object_from_external(source)
		assert_that(related, has_property('creator', is_(u'Steven M. Gillon')))
		assert_that(related, has_property('byline', is_(u'Steven M. Gillon')))
		assert_that(related, has_property('label', is_(u'The Critical Year: 1968')))
		assert_that(related, has_property('type', is_(u"application/vnd.nextthought.content")))
		assert_that(related, has_property('icon', is_(u"resources/LSTD1153_S_2015_History_United_States_1865_to_Present/420c90cea830984c7260c255692e6cd794e2b281/fd35e23767020999111e1f49239199b4c5eff23e.jpg")))
		assert_that(related, has_property('desc', is_(u"A look at how the U.S. came to a crossroads in 1968, when faced with the Vietnam War, political partisanship, racial violence, and social upheaval.")))
		assert_that(related, has_property('mimeType', is_(u"application/vnd.nextthought.relatedworkref")))
		assert_that(related, has_property('target', is_(u"tag:nextthought.com,2011-10:OU-HTML-LSTD1153_S_2015_History_United_States_1865_to_Present.reading:12.3_1")))
		assert_that(related, has_property('href', is_(u"tag:nextthought.com,2011-10:OU-HTML-LSTD1153_S_2015_History_United_States_1865_to_Present.reading:12.3_1")))
		assert_that(related, has_property('ntiid', is_(u"tag:nextthought.com,2011-10:OU-RelatedWork-LSTD1153_S_2015_History_United_States_1865_to_Present.relatedwork.relwk:12.3_1_Critical_Year_1968")))

		ext_obj = to_external_object(related)
		for k, v in original.items():
			assert_that(ext_obj, has_entry(k, is_(v)))

		assert_that(ext_obj, has_key('MimeType'))
		assert_that(ext_obj, has_key('Class'))
		assert_that(ext_obj, has_key('NTIID'))
