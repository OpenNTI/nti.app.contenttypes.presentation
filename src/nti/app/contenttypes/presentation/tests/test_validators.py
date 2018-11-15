#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import same_instance

from zope import component

from nti.contenttypes.calendar.interfaces import ICalendar

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.calendar import NTICalendarEventRef

from nti.contenttypes.presentation.interfaces import INTICalendarEventRef

from nti.app.contenttypes.presentation.interfaces import IItemRefValidator

from nti.app.products.courseware.calendar.model import CourseCalendarEvent

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
import nti.dataserver.tests.mock_dataserver as mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid


class TestValidators(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_calendar_event_ref(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            calendar = ICalendar(course)
            event = calendar.store_event(CourseCalendarEvent(title=u'abc'))
            ref = NTICalendarEventRef(target=event.ntiid)

            validator = IItemRefValidator(ref, None)
            assert_that(validator, is_not(None))
            assert_that(validator.validate(), is_(True))

            ref.target = u'tag:nextthought.com,2011-10:NTI-OID-system_2018000000'
            validator = IItemRefValidator(ref, None)
            assert_that(validator, is_not(None))
            assert_that(validator.validate(), is_(False))
