#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.authentication.interfaces import IUnauthenticatedPrincipal

from zope.security.interfaces import NoInteraction
from zope.security.management import getInteraction

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

from nti.contenttypes.courses.utils import get_any_enrollment

from nti.contenttypes.presentation.interfaces import PUBLIC
from nti.contenttypes.presentation.interfaces import CREDIT
from nti.contenttypes.presentation.interfaces import EVERYONE
from nti.contenttypes.presentation.interfaces import PURCHASED

from nti.contenttypes.presentation.interfaces import IPresentationVisibility

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
	try:
		return getInteraction().participations[0].principal
	except (NoInteraction, IndexError, AttributeError):
		return None

def _get_scope(user, context, record):
	if user is not None:
		record = get_enrollment_record(context, user) if record is None else record
	else:
		user = get_participation_principal()

	scope = record.Scope if record is not None else None
	if 		scope is None \
		and IAnonymouslyAccessibleCourseInstance.providedBy( context ) \
		and IUnauthenticatedPrincipal.providedBy( user ):
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
			# Our item is scoped and not-visible to us, but editors always have access.
			return has_permission(ACT_CONTENT_EDIT, context)
	return True

def get_scope_term(name):
	return ENROLLMENT_SCOPE_MAP.get(name)

def get_implied_by_scopes(scopes=()):
	result = set()
	for scope in scopes or ():
		result.add(scope)
		if scope == ES_ALL:
			result.discard(scope)
			result.update(ENROLLMENT_SCOPE_MAP.keys())
			break
		else:
			es = ENROLLMENT_SCOPE_MAP.get(scope)
			result.update(es.implied_by if es is not None else ())
	return result

def resolve_discussion_course_bundle(user, item, context=None, record=None):
	"""
	return a tuple of course discussion and preferred topic according the discussion ref
	and user enrollment or None

	:param item: A discussion ref object
	:param context: An object that can be adpated to a course
	:param record: Enrollment record if avaiable
	"""

	context = item if context is None else item
	record = get_enrollment_record(context, user) if record is None else record
	if record is None:
		logger.warn("No enrollment record for user %s under %s", user, context)
		return None

	# enrollment scope. When scope is equals to 'All' it means user is an instructor
	scope = record.Scope

	# get course pointed by the discussion ref
	course = get_course_for_discussion(item, context=record.CourseInstance)
	if course is None:
		logger.warn("No course found for discussion %s", item)
		return None

	# if course is a subinstance, make sure we are enrolled in it and
	# we are not an instructor
	if 		ICourseSubInstance.providedBy(course) \
		and	scope != ES_ALL \
		and course != record.CourseInstance:
		return None

	# get course discussion
	key = get_discussion_key(item)
	discussion = ICourseDiscussions(course).get(key) if key else None
	scopes = get_implied_by_scopes(discussion.scopes) if discussion is not None else ()
	logger.debug("Implied scopes for %s are %s", key, scopes)

	if		(not scope) \
		or	(not scopes) \
		or	(scope != ES_ALL and ES_ALL not in scopes and scope not in scopes):
		logger.warn("User scope %s did not match implied scopes %s", scope, scopes)
		return None
	else:
		topic = None
		topic_key = get_topic_key(discussion)
		topic_title = make_specific_safe( discussion.title )
		m_scope = ES_ALL if scope == ES_ALL else ENROLLMENT_LINEAGE_MAP.get(scope)[0]
		m_scope_term = get_scope_term(m_scope) if m_scope != ES_ALL else None
		m_scope_implies = set(getattr(m_scope_term, 'implies', None) or ())
		for v in course.Discussions.values():
			# check the forum scopes against the mapped enrollment scope
			forum_scopes = get_forum_scopes(v) if m_scope != ES_ALL else ()
			if 	(m_scope == ES_ALL or
				 m_scope in forum_scopes or
				 m_scope_implies.intersection(forum_scopes)) and \
				(topic_key in v or topic_title in v):
				topic = v[topic_key]  # found the topic
				break
		if topic is not None:
			return (discussion, topic)
		return None
