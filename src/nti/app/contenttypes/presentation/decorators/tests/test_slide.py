#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import has_length
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


class TestSlide(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_slide(self):
        path = os.path.join(os.path.dirname(__file__), 'slide.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
            original = copy.deepcopy(source)

        slide = create_object_from_external(source)
        assert_that(slide, has_property('number', is_(11)))
        assert_that(slide, has_property('end', is_(398.0)))
        assert_that(slide, has_property('start', is_(354.0)))
        assert_that(slide, 
                    has_property("deck", "tag:nextthought.com,2011-10:OU-NTISlideDeck-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Insertion_Sort"))
        assert_that(slide, 
                    has_property('mimeType', is_("application/vnd.nextthought.slide")))
        assert_that(slide, 
                    has_property('ntiid', is_("tag:nextthought.com,2011-10:OU-NTISlide-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Insertion_Sort_slide_11")))
        assert_that(slide, 
                    has_property('image', is_("resources/CS1323_S_2015_Intro_to_Computer_Programming/e3573369b10854aea33ccaf31260b51ff1384069/fd35e23767020999111e1f49239199b4c5eff23e.png")))

        ext_obj = to_external_object(slide)
        for k, v in original.items():
            assert_that(ext_obj, has_entry(k, is_(v)))

        assert_that(ext_obj, has_key('MimeType'))
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, has_key('NTIID'))

    def test_ntislidevideo(self):
        path = os.path.join(os.path.dirname(__file__), 'ntislidevideo.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
            original = copy.deepcopy(source)

        slide = create_object_from_external(source)
        assert_that(slide, 
                    has_property('thumbnail', is_("//www.kaltura.com/p/1500101/thumbnail/entry_id/0_06h42bu6/width/640/")))
        assert_that(slide, has_property('creator', is_("Deborah Trytten")))
        assert_that(slide, has_property('byline', is_("Deborah Trytten")))
        assert_that(slide, 
                    has_property('title', is_("Install Software on Macintosh")))
        assert_that(slide, 
                    has_property("deck", "tag:nextthought.com,2011-10:OU-NTISlideDeck-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Install_Mac"))
        assert_that(slide, 
                    has_property('mimeType', is_("application/vnd.nextthought.ntislidevideo")))
        assert_that(slide, 
                    has_property('ntiid', is_("tag:nextthought.com,2011-10:OU-NTISlideVideo-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Install_Mac_video")))
        assert_that(slide,
                    has_property('video', is_("tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_S_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.02_Mac")))

        ext_obj = to_external_object(slide)
        for k, v in original.items():
            assert_that(ext_obj, has_entry(k, is_(v)))

        assert_that(ext_obj, has_key('MimeType'))
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, has_key('NTIID'))

    def test_ntislidedeck(self):
        path = os.path.join(os.path.dirname(__file__), 'ntislidedeck.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))

        deck = create_object_from_external(source)
        assert_that(deck, has_property('creator', is_("Deborah Trytten")))
        assert_that(deck, has_property('byline', is_("Deborah Trytten")))
        assert_that(deck, 
                    has_property('title', is_("Install Software on a Macintosh")))
        assert_that(deck, 
                    has_property("id", is_("tag:nextthought.com,2011-10:OU-NTISlideDeck-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Install_Mac")))
        assert_that(deck, 
                    has_property('ntiid', is_("tag:nextthought.com,2011-10:OU-NTISlideDeck-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Install_Mac")))
        assert_that(deck,
                    has_property('mimeType', is_("application/vnd.nextthought.ntislidedeck")))
        assert_that(deck, has_property('videos', has_length(1)))
        assert_that(deck, has_property('slides', has_length(19)))

        ext_obj = to_external_object(deck)
        assert_that(ext_obj, has_entry('creator', is_("Deborah Trytten")))
        assert_that(ext_obj, has_entry('byline', is_("Deborah Trytten")))
        assert_that(ext_obj, 
                    has_entry('title', is_("Install Software on a Macintosh")))
        assert_that(ext_obj,
                    has_entry('MimeType', is_("application/vnd.nextthought.ntislidedeck")))
        assert_that(ext_obj, 
                    has_entry('ntiid', is_("tag:nextthought.com,2011-10:OU-NTISlideDeck-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Install_Mac")))
        assert_that(ext_obj, 
                    has_entry('slidedeckid', is_("tag:nextthought.com,2011-10:OU-NTISlideDeck-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Install_Mac")))
        assert_that(ext_obj, has_entry('Videos', has_length(1)))
        assert_that(ext_obj, has_entry('Slides', has_length(19)))

        assert_that(ext_obj, has_key('MimeType'))
        assert_that(ext_obj, has_key('Class'))
        assert_that(ext_obj, has_key('NTIID'))

        slide = deck.Slides[0]
        assert_that(deck.remove(slide), is_(True))
        assert_that(deck.Slides, has_length(18))

        video = deck.Videos[0]
        assert_that(deck.remove(video), is_(True))
        assert_that(deck.Videos, has_length(0))
