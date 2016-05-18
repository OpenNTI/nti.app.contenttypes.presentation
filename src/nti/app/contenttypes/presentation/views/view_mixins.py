#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import hashlib

from pyramid import httpexceptions as hexc

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.appserver.pyramid_authorization import has_permission

from nti.coremetadata.interfaces import IPublishable

from nti.dataserver import authorization as nauth

from nti.ntiids.ntiids import is_valid_ntiid_string

def hexdigest(data, hasher=None):
	hasher = hashlib.sha256() if hasher is None else hasher
	hasher.update(data)
	result = hasher.hexdigest()
	return result

class PublishVisibilityMixin(object):

	def _is_visible(self, item):
		"""
		Define whether this possibly publishable object is visible to the
		remote user.
		"""
		return (not IPublishable.providedBy(item)
				or 	item.is_published()
				or	has_permission(nauth.ACT_CONTENT_EDIT, item, self.request))

class NTIIDPathMixin(object):

	def _get_ntiid(self):
		"""
		Looks for a user supplied ntiid in the context path: '.../ntiid/<ntiid>'.
		"""
		result = None
		if self.request.subpath and self.request.subpath[0] == 'ntiid':
			try:
				result = self.request.subpath[1]
			except (TypeError, IndexError):
				pass
		if result is None or not is_valid_ntiid_string(result):
			raise hexc.HTTPUnprocessableEntity(_('Invalid ntiid %s' % result))
		return result
