#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.products.courseware.discussions import get_forum_scopes

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_MAP
from nti.contenttypes.courses.interfaces import ENROLLMENT_LINEAGE_MAP

from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.utils import get_topic_key
from nti.contenttypes.courses.discussions.utils import get_discussion_key
from nti.contenttypes.courses.discussions.utils import get_course_for_discussion

from nti.contenttypes.courses.utils import get_any_enrollment

from nti.contenttypes.presentation.interfaces import PUBLIC
from nti.contenttypes.presentation.interfaces import CREDIT
from nti.contenttypes.presentation.interfaces import EVERYONE
from nti.contenttypes.presentation.interfaces import PURCHASED

from nti.contenttypes.presentation.interfaces import IPresentationVisibility

# re-export
from .common import yield_sync_courses

# re-export
from .asset import intid_register
from .asset import add_2_connection
from .asset import make_asset_ntiid
from .asset import registry_by_name
from .asset import component_registry
from .asset import create_lesson_4_node
from .asset import remove_presentation_asset
from .asset import notify_removed as notify_asset_removed

# re-export
from .course import get_courses
from .course import get_course_packages
from .course import get_enrollment_record
from .course import get_presentation_asset_courses
from .course import get_entry_by_relative_path_parts
from .course import get_course_by_relative_path_parts
from .course import get_presentation_asset_containers

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

def is_item_visible(item, user, context=None, record=None):
	context = item if context is None else context
	user_visibility = get_user_visibility(user)
	if item.visibility != EVERYONE and user_visibility != item.visibility:
		record = get_enrollment_record(context, user) if record is None else record
		scope = record.Scope if record is not None else None
		if scope != ES_ALL and get_visibility_for_scope(scope) != item.visibility:
			return False
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
		return None
	# enrollment scope. When scope is equals to 'All' it means user is an instructor
	scope = record.Scope

	# get course pointed by the discussion ref
	course = get_course_for_discussion(item, context=record.CourseInstance)

	# if course is a subinstance, make sure we are enrolled in it and
	# we are not an instructor
	if 	ICourseSubInstance.providedBy(course) and \
		scope != ES_ALL and course != record.CourseInstance:
		return None

	# get course discussion
	key = get_discussion_key(item)
	discussion = ICourseDiscussions(course).get(key) if key else None
	scopes = get_implied_by_scopes(discussion.scopes) if discussion is not None else ()

	if	(not scope) or \
		(not scopes) or \
		(scope != ES_ALL and ES_ALL not in scopes and scope not in scopes):
		return None
	else:
		topic = None
		topic_key = get_topic_key(discussion)
		m_scope = ES_ALL if scope == ES_ALL else ENROLLMENT_LINEAGE_MAP.get(scope)[0]
		m_scope_term = get_scope_term(m_scope) if m_scope != ES_ALL else None
		m_scope_implies = set(getattr(m_scope_term, 'implies', None) or ())
		for v in course.Discussions.values():
			# check the forum scopes against the mapped enrollment scope
			forum_scopes = get_forum_scopes(v) if m_scope != ES_ALL else ()
			if 	(m_scope == ES_ALL or
				 m_scope in forum_scopes or
				 m_scope_implies.intersection(forum_scopes)) and \
				topic_key in v:
				topic = v[topic_key]  # found the topic
				break
		return (discussion, topic)
