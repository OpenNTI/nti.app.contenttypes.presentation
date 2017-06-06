#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory(__name__)

from zope import component

from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation import iface_of_asset as iface_of_thing

#: View to store/fetch presentation assets.
VIEW_ASSETS = 'assets'

# View to move objects underneath a group/node.
VIEW_NODE_MOVE = 'move'

#: View to fetch contents of a lesson.
VIEW_CONTENTS = 'contents'

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
