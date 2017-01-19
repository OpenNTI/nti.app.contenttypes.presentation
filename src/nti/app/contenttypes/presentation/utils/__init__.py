#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.authentication.interfaces import IUnauthenticatedPrincipal

# re-export
from nti.app.contenttypes.presentation.utils.asset import db_connection
from nti.app.contenttypes.presentation.utils.asset import component_site
from nti.app.contenttypes.presentation.utils.asset import intid_register
from nti.app.contenttypes.presentation.utils.asset import add_2_connection
from nti.app.contenttypes.presentation.utils.asset import make_asset_ntiid
from nti.app.contenttypes.presentation.utils.asset import registry_by_name
from nti.app.contenttypes.presentation.utils.asset import component_registry
from nti.app.contenttypes.presentation.utils.asset import create_lesson_4_node
from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset
from nti.app.contenttypes.presentation.utils.asset import notify_removed as notify_asset_removed

# re-export
from nti.app.contenttypes.presentation.utils.common import yield_sync_courses

# re-export
from nti.app.contenttypes.presentation.utils.course import get_courses
from nti.app.contenttypes.presentation.utils.course import get_enrollment_record
from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_courses
from nti.app.contenttypes.presentation.utils.course import get_entry_by_relative_path_parts
from nti.app.contenttypes.presentation.utils.course import get_course_by_relative_path_parts
from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_containers

from nti.app.products.courseware.discussions import get_forum_scopes

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_MAP
from nti.contenttypes.courses.interfaces import ENROLLMENT_LINEAGE_MAP

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.utils import get_topic_key
from nti.contenttypes.courses.discussions.utils import get_discussion_key
from nti.contenttypes.courses.discussions.utils import get_course_for_discussion

from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance

# re-export
from nti.contenttypes.courses.discussions.utils import resolve_discussion_course_bundle

from nti.contenttypes.presentation.interfaces import PUBLIC
from nti.contenttypes.presentation.interfaces import CREDIT
from nti.contenttypes.presentation.interfaces import EVERYONE
from nti.contenttypes.presentation.interfaces import PURCHASED

from nti.contenttypes.presentation.interfaces import IPresentationVisibility

from nti.coremetadata.utils import current_principal

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.ntiids.ntiids import make_specific_safe

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
        record = get_enrollment_record(
            context, user) if record is None else record
    else:
        user = get_participation_principal()

    scope = record.Scope if record is not None else None
    if         scope is None \
            and IAnonymouslyAccessibleCourseInstance.providedBy(context) \
            and IUnauthenticatedPrincipal.providedBy(user):
        # If our context allows anonymous access, we should treat
        # anonymous users as Open for visibility checks.
        scope = ES_PUBLIC
    return scope


def is_item_visible(item, user, context=None, record=None):
    context = item if context is None else context
    user_visibility = get_user_visibility(user)
    # If it has non-everyone visibility, unequal to our user's, check scope.
    if 		item.visibility \
            and item.visibility != EVERYONE \
            and user_visibility != item.visibility:
        scope = _get_scope(user, context, record)
        if scope != ES_ALL and get_visibility_for_scope(scope) != item.visibility:
            # Our item is scoped and not-visible to us, but editors always have
            # access.
            return has_permission(ACT_CONTENT_EDIT, context)
    return True
