#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory(__name__)

from zope import component

from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation import iface_of_asset as iface_of_thing

#: Course assets storage folder
ASSETS_FOLDER = 'assets'

VIEW_ASSETS = 'assets'
VIEW_NODE_MOVE = 'move'
VIEW_CONTENTS = 'contents'
VIEW_NODE_CONTENTS = 'contents'
VIEW_OVERVIEW_CONTENT = "overview-content"
VIEW_OVERVIEW_SUMMARY = "overview-summary"
VIEW_ORDERED_CONTENTS = 'ordered-contents'
