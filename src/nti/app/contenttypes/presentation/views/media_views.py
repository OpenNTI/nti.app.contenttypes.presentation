#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import sys

from zope import component
from zope import lifecycleevent

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import update_object_from_external_object

from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.base._compat import text_

from nti.contentindexing.media.interfaces import IVideoTranscriptParser

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTITranscript

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.namedfile.file import NamedBlobFile

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

TEXT_VTT = "text/vtt"


@view_config(context=INTIMedia)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name='transcripts',
               permission=nauth.ACT_READ)
class MediaTranscriptsGetView(AbstractAuthenticatedView):

    def __call__(self):
        result = LocatedExternalDict()
        result[ITEMS] = items = list(self.context.transcripts or ())
        result[ITEM_COUNT] = result[TOTAL] = len(items)
        return result


@view_config(context=INTITranscript)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_READ)
class NTITranscriptPutView(AbstractAuthenticatedView,
                           ModeledContentEditRequestUtilsMixin,
                           ModeledContentUploadRequestUtilsMixin):

    def parse_transcript(self, content, name=TEXT_VTT):
        parser = component.getUtility(IVideoTranscriptParser, name=name)
        transcript = parser.parse(text_(content))
        assert transcript, "Empty transcript"
        return transcript

    def __call__(self):
        theObject = self.context
        self._check_object_exists(theObject)
        self._check_object_unmodified_since(theObject)

        externalValue = self.readInput()
        if externalValue:  # something to update
            theObject = update_object_from_external_object(theObject,
                                                           externalValue,
                                                           notify=False,
                                                           request=self.request)

        if not theObject.src:
            sources = get_all_sources(self.request)
            if not sources:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"No transcript source was specified."),
                                     'code': 'NoTranscriptSpecified',
                                 },
                                 None)
            name, source = next(iter(sources.items()))
            content = text_(source.read())
            try:
                self.parse_transcript(content)
            except Exception as e:
                exc_info = sys.exc_info()
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"Invalid transcript source."),
                                     'code': 'InvalidTranscript',
                                     'message': str(e)
                                 },
                                 exc_info[2])
            source = NamedBlobFile(data=content,
                                   contentType=TEXT_VTT,
                                   filename=name)
            theObject.src = source
        lifecycleevent.modified(theObject)
        return theObject
