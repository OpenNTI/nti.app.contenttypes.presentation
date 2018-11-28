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

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contenttypes.presentation.interfaces import INTICalendarEventRef

from nti.externalization.interfaces import IExternalObjectDecorator

from nti.ntiids.ntiids import find_object_with_ntiid

logger = __import__('logging').getLogger(__name__)


@component.adapter(INTICalendarEventRef)
@interface.implementer(IExternalObjectDecorator)
class _CalendarEventDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _do_decorate_external(self, context, external):
        external['CalendarEvent'] = find_object_with_ntiid(context.target)
