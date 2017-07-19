#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import ILocation

from nti.app.contenttypes.presentation.decorators import VIEW_TRANSCRIPTS

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.presentation.interfaces import INTIMedia

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS


@component.adapter(INTIMedia)
@interface.implementer(IExternalObjectDecorator)
class _MediaLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    @Lazy
    def _acl_decoration(self):
        return getattr(self.request, 'acl_decoration', True)

    def _predicate(self, context, result):
        return self._acl_decoration \
           and self._is_authenticated \
           and has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for name, method in ( (VIEW_TRANSCRIPTS, 'GET'),
                              ('transcript', 'POST'),
                              ('clear_transcripts', 'POST'), ):
            link = Link(context, 
                        rel=name,
                        method=method,
                        elements=('@@%s' % name,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)
