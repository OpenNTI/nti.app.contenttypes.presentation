#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory(__name__)

from zope import component

from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation import interface_of_asset as iface_of_thing

#: Path component designating ICoursePresentationAssets
VIEW_ASSETS = 'assets'

#: View to get course content library information
VIEW_COURSE_CONTENT_LIBRARY_SUMMARY = 'CourseContentLibrarySummary'

# View to move objects underneath a group/node.
VIEW_NODE_MOVE = 'move'

#: View to fetch contents of a lesson.
VIEW_CONTENTS = 'contents'

# View to fetch transcript of a media object.
VIEW_TRANSCRIPTS = 'transcripts'

# View to fetch contents of a node.
VIEW_NODE_CONTENTS = 'contents'

#: View to fetch the lesson overview of a content node.
VIEW_OVERVIEW_CONTENT = "overview-content"

#: View to summarize UGD counts in a content node.
VIEW_OVERVIEW_SUMMARY = "overview-summary"

#: View to insert/delete by index.
VIEW_ORDERED_CONTENTS = 'ordered-contents'

#: View to remove all refs pointing at target in lessons.
VIEW_LESSON_REMOVE_REFS = 'RemoveRefs'

#: View to gather lesson progress for the remote user.
VIEW_LESSON_PROGRESS = 'Progress'

#: View to gather lesson progress stats
VIEW_LESSON_PROGRESS_STATS = 'ProgressStatisticsByItem'

