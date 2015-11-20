#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory

from .. import VIEW_NODE_CONTENTS
from .. import VIEW_OVERVIEW_CONTENT
from .. import VIEW_OVERVIEW_SUMMARY

ORDERED_CONTENTS = 'ordered-contents'

LEGACY_UAS_40 = ("NTIFoundation DataLoader NextThought/1.0",
				 "NTIFoundation DataLoader NextThought/1.1.",
				 "NTIFoundation DataLoader NextThought/1.2.",
				 "NTIFoundation DataLoader NextThought/1.3.",
				 "NTIFoundation DataLoader NextThought/1.4.0")

def is_legacy_uas(request, legacy_uas):
	ua = request.environ.get(b'HTTP_USER_AGENT', '')
	if not ua:
		return False

	for lua in legacy_uas:
		if ua.startswith(lua):
			return True
	return False
