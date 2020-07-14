#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

import time

from zope.authentication.interfaces import IUnauthenticatedPrincipal

from zope.security.interfaces import IParticipation
from zope.security.management import endInteraction
from zope.security.management import newInteraction
from zope.security.management import restoreInteraction

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE
from nti.contenttypes.courses.interfaces import NTI_COURSE_OUTLINE_NODE

from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance

from nti.contenttypes.courses.utils import get_user_or_instructor_enrollment_record

from nti.contenttypes.presentation import NTI

from nti.contenttypes.presentation.interfaces import PUBLIC
from nti.contenttypes.presentation.interfaces import CREDIT
from nti.contenttypes.presentation.interfaces import EVERYONE
from nti.contenttypes.presentation.interfaces import PURCHASED

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import IPresentationVisibility

from nti.coremetadata.utils import current_principal

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization_acl import has_permission

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.zodb.containers import time_to_64bit_int

logger = __import__('logging').getLogger(__name__)


#: Visibility scope map
VISIBILITY_SCOPE_MAP = {
    ES_ALL: EVERYONE,
    ES_PUBLIC: PUBLIC,
    ES_CREDIT: CREDIT,
    ES_PURCHASED: PURCHASED,
    ES_CREDIT_DEGREE: CREDIT,
    ES_CREDIT_NONDEGREE: CREDIT,
}


def get_visibility_for_scope(scope):
    return VISIBILITY_SCOPE_MAP.get(scope)


def get_user_visibility(user):
    adapted = IPresentationVisibility(user, None)
    result = adapted.visibility() if adapted is not None else None
    return result


def get_participation_principal():
    return current_principal(False)


def _get_scope(user, context, record):
    if user is not None:
        if record is None:
            record = get_user_or_instructor_enrollment_record(context, user)
    else:
        user = get_participation_principal()

    scope = record.Scope if record is not None else None
    if      scope is None \
        and IAnonymouslyAccessibleCourseInstance.providedBy(context) \
        and IUnauthenticatedPrincipal.providedBy(user):
        # If our context allows anonymous access, we should treat
        # anonymous users as Open for visibility checks.
        scope = ES_PUBLIC
    return scope


def is_item_visible(item, user, context=None, record=None):
    result = True
    if not IVisible.providedBy(item):
        return result
    context = item if context is None else context
    user_visibility = get_user_visibility(user)
    # If it has non-everyone visibility, unequal to our user's, check scope.
    if      item.visibility \
        and item.visibility != EVERYONE \
        and user_visibility != item.visibility:
        scope = _get_scope(user, context, record)
        if scope != ES_ALL and get_visibility_for_scope(scope) != item.visibility:
            # Our item is scoped and not-visible to us, but editors always have
            # access. We may be checking this on behalf of another user.
            result = has_permission(ACT_CONTENT_EDIT, context, user.username)
    return result


def generate_node_ntiid(parent_node, catalog_entry, user):
    """
    Build an ntiid for our new node, making sure we don't conflict
    with other ntiids. To help ensure this (and to avoid collisions
    with deleted nodes), we use the creator and a timestamp.
    """
    try:
        base = parent_node.ntiid
    except AttributeError:
        # Outline, use catalog entry
        entry = catalog_entry
        base = entry.ntiid if entry is not None else None

    provider = get_provider(base) or NTI
    current_time = time_to_64bit_int(time.time())
    specific_base = u'%s.%s.%s' % (get_specific(base),
                                   user.username,
                                   current_time)
    idx = 0
    while True:
        specific = specific_base + u".%s" % idx
        specific = make_specific_safe(specific)
        ntiid = make_ntiid(nttype=NTI_COURSE_OUTLINE_NODE,
                           base=base,
                           provider=provider,
                           specific=specific)
        if ntiid not in parent_node:
            break
        idx += 1
    return ntiid
