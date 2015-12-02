#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.location.interfaces import ILocation

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields

from nti.links.links import Link

from .. import MessageFactory

from .. import VIEW_ASSETS
from .. import VIEW_NODE_MOVE
from .. import VIEW_NODE_CONTENTS
from .. import VIEW_OVERVIEW_CONTENT
from .. import VIEW_OVERVIEW_SUMMARY

LINKS = StandardExternalFields.LINKS

ORDERED_CONTENTS = 'ordered-contents'

LEGACY_UAS_20 = ("NTIFoundation DataLoader NextThought/1.0",
				 "NTIFoundation DataLoader NextThought/1.1",
				 "NTIFoundation DataLoader NextThought/1.1.1",
				 "NTIFoundation DataLoader NextThought/1.2.")

LEGACY_UAS_40 = LEGACY_UAS_20 + \
				("NTIFoundation DataLoader NextThought/1.3.",
				 "NTIFoundation DataLoader NextThought/1.4.0")

def is_legacy_uas(request, legacy_uas=LEGACY_UAS_40):
	ua = request.environ.get(b'HTTP_USER_AGENT', '')
	if not ua:
		return False

	for lua in legacy_uas:
		if ua.startswith(lua):
			return True
	return False

class _AbstractMoveLinkDecorator( AbstractAuthenticatedRequestAwareDecorator ):

	def _predicate(self, context, result):
		return 		self._is_authenticated \
				and has_permission(ACT_CONTENT_EDIT, context, self.request)

	def _do_decorate_external(self, context, result):
		links = result.setdefault(LINKS, [])
		link = Link(context, rel=VIEW_NODE_MOVE, elements=(VIEW_NODE_MOVE,))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		links.append(link)
