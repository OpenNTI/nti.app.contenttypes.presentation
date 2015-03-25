#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urlparse import urljoin

from zope import component
from zope import interface
from zope.location.interfaces import ILocation

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link
from nti.links.externalization import render_link

LINKS = StandardExternalFields.LINKS

from . import VIEW_OVERVIEW_CONTENT

@component.adapter(ICourseOutlineContentNode)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineContentNodeLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	_BAD_UAS = ( "NTIFoundation DataLoader NextThought/1.0",
				 "NTIFoundation DataLoader NextThought/1.1.0",
				 "NTIFoundation DataLoader NextThought/1.1.1",
				 "NTIFoundation DataLoader NextThought/1.2.0" )
	
	@property
	def _is_legacy_iPad(self):
		if self.request is None:
			return False
		
		ua = self.request.environ.get('HTTP_USER_AGENT', '')
		if not ua:
			return False

		for bua in self._BAD_UAS:
			if ua.startswith(bua):
				return True
		return False
	
	def _predicate(self, context, result):
		return True

	def _legacy_decorate_external(self, context, result):
		if context.src:
			library = component.queryUtility(IContentPackageLibrary)
			paths = library.pathToNTIID(context.ContentNTIID) if library else ()
			if paths:
				href = IContentUnitHrefMapper( paths[-1].key ).href
				href = urljoin(href, context.src)
				# set link for overview
				links = result.setdefault(LINKS, [])
				link = Link(href, rel=VIEW_OVERVIEW_CONTENT,
							ignore_properties_of_target=True)
				interface.alsoProvides(link, ILocation)
				link.__name__ = ''
				link.__parent__ = context
				links.append(link)
				return True
		return False

	def _overview_decorate_external(self, context, result):
		try:
			ntiid = context.LessonOverviewNTIID
			lesson = component.getUtility(INTILessonOverview, name=ntiid) if ntiid else None
			if lesson is not None:
				links = result.setdefault(LINKS, [])
				if not self._is_legacy_iPad:
					link = Link(context, rel=VIEW_OVERVIEW_CONTENT,
								elements=(VIEW_OVERVIEW_CONTENT,) )
				else:
					try:
						link = Link(context, elements=(VIEW_OVERVIEW_CONTENT,))
						href = render_link( link )['href']
						url = urljoin(self.request.host_url, href)
						link = Link(url, rel=VIEW_OVERVIEW_CONTENT,
									ignore_properties_of_target=True)
						interface.alsoProvides(link, ILocation)
						link.__name__ = ''
						link.__parent__ = context
					except (KeyError, ValueError, AssertionError):
						return False
				links.append(link)
				return True
		except AttributeError:
			pass
		return False
	
	def _do_decorate_external(self, context, result):		
		if not self._overview_decorate_external(context, result):
			self._legacy_decorate_external(context, result)
