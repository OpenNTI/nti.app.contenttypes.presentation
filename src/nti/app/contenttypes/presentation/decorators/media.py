#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import ILocation

from nti.app.contenttypes.presentation.decorators import VIEW_TRANSCRIPTS

from nti.app.contenttypes.presentation.interfaces import ICoursePresentationAssets

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTITranscript
from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import IUserCreatedTranscript

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.interfaces import ILinkExternalHrefOnly

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)

@component.adapter(INTIMedia)
@interface.implementer(IExternalObjectDecorator)
class _MediaHrefRewriter(AbstractAuthenticatedRequestAwareDecorator):
    """
    When we can, we want access to our media (all assets?) to come
    through our assets location. Ideally we could just use
    IShouldHaveTraversablePath to accomplish this, but there are a few
    things to work out prior to that. Primarily we need to have
    ICoursePresnetationAssets be in the lineage of the assets and have
    a plan for how to acquire them appropriately from parent courses
    when possible. This might makes sense to tackle in tandom with
    registering these things in a ISiteManager tied to the course
    instead of the global site.
    """

    @Lazy
    def course(self):
        return ICourseInstance(self.request, None)
    
    def _predicate(self, context, result):
        return self.course is not None

    def _do_decorate_external(self, context, result):
        assets = ICoursePresentationAssets(self.course)
        link = Link(assets, elements=(context.ntiid,))
        interface.alsoProvides(link, ILinkExternalHrefOnly)
        result['href'] = link
        

@component.adapter(INTIMedia)
@interface.implementer(IExternalObjectDecorator)
class _MediaLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    @Lazy
    def _acl_decoration(self):
        return getattr(self.request, 'acl_decoration', True)

    def _predicate(self, context, unused_result):
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
        if IUserCreatedAsset.providedBy(context):
            link = Link(context, rel='delete', method='DELETE')
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(INTITranscript)
@interface.implementer(IExternalObjectDecorator)
class _TranscriptLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    @Lazy
    def _acl_decoration(self):
        return getattr(self.request, 'acl_decoration', True)

    def _predicate(self, context, unused_result):
        return self._acl_decoration \
           and self._is_authenticated \
           and has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _do_decorate_external(self, context, result):
        if IUserCreatedTranscript.providedBy(context):
            _links = result.setdefault(LINKS, [])
            link = Link(context, rel='edit', method='PUT')
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)
