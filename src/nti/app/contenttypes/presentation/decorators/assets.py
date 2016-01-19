#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from urlparse import urljoin

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from pyramid.interfaces import IRequest

from nti.app.contentlibrary.utils import get_item_content_units

from nti.app.contenttypes.presentation.decorators import LEGACY_UAS_40
from nti.app.contenttypes.presentation.decorators import VIEW_ORDERED_CONTENTS

from nti.app.contenttypes.presentation.decorators import is_legacy_uas
from nti.app.contenttypes.presentation.decorators import _AbstractMoveLinkDecorator

from nti.app.contenttypes.presentation.utils import is_item_visible
from nti.app.contenttypes.presentation.utils import resolve_discussion_course_bundle
from nti.app.contenttypes.presentation.utils import get_enrollment_record as get_any_enrollment_record

from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_TOPIC
from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment

from nti.common.property import Lazy

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contenttypes.courses.interfaces import OPEN
from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import IN_CLASS
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ENROLLMENT_LINEAGE_MAP
from nti.contenttypes.courses.interfaces import get_course_assessment_predicate_for_user

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import IMediaRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIAudioRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIQuestionRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import to_external_ntiid_oid

from nti.externalization.singleton import SingletonDecorator

from nti.links.links import Link

from nti.ntiids.ntiids import get_type
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_provider_safe

NTIID = StandardExternalFields.NTIID
LINKS = StandardExternalFields.LINKS
ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE
IN_CLASS_SAFE = make_provider_safe(IN_CLASS)
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

#: Legacy ipad key for item video rolls
COLLECTION_ITEMS = u'collectionItems'

@component.adapter(IPresentationAsset)
@interface.implementer(IExternalMappingDecorator)
class _PresentationAssetEditLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	@Lazy
	def _acl_decoration(self):
		result = getattr(self.request, 'acl_decoration', True)
		return result

	def _has_edit_link(self, result):
		for lnk in result.get(LINKS) or ():
			if getattr(lnk, 'rel', None) == 'edit':
				return True
		return False

	def _predicate(self, context, result):
		return 		self._acl_decoration \
				and self._is_authenticated \
				and	not self._has_edit_link(result) \
				and has_permission(ACT_CONTENT_EDIT, context, self.request)

	def _do_decorate_external(self, context, result):
		_links = result.setdefault(LINKS, [])
		link = Link(context, rel='edit')
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		_links.append(link)

@component.adapter(INTILessonOverview)
@interface.implementer(IExternalMappingDecorator)
class _LessonMoveLinkDecorator(_AbstractMoveLinkDecorator):
	pass

@component.adapter(INTILessonOverview)
@component.adapter(INTICourseOverviewGroup)
@interface.implementer(IExternalMappingDecorator)
class _NTIAssetOrderedContentsLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	@Lazy
	def _acl_decoration(self):
		result = getattr(self.request, 'acl_decoration', True)
		return result

	def _predicate(self, context, result):
		return 		self._acl_decoration \
				and self._is_authenticated \
				and has_permission(ACT_CONTENT_EDIT, context, self.request)

	def _do_decorate_external(self, context, result):
		links = result.setdefault(LINKS, [])
		link = Link(context, rel=VIEW_ORDERED_CONTENTS, elements=('contents',))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		links.append(link)

@interface.implementer(IExternalObjectDecorator)
class _VisibleMixinDecorator(AbstractAuthenticatedRequestAwareDecorator):

	_record = None

	def record(self, context):
		if self._record is None:
			self._record = get_any_enrollment_record(context, self.remoteUser)
		return self._record

	def _handle_media_ref(self, items, item, idx):
		source = INTIMedia(item, None)
		if source is not None:
			items[idx] = to_external_object(source)
			return True
		return False

	def _allow_visible(self, context, item):
		record = self.record(context)
		result = is_item_visible(item, user=self.remoteUser,
								 context=context, record=record)
		return result

	def _decorate_external_impl(self, context, result):
		pass

	def _do_decorate_external(self, context, result):
		try:
			__traceback_info__ = context
			self._decorate_external_impl(context, result)
		except Exception:
			logger.exception("Error while decorating asset")

@component.adapter(INTIMediaRoll)
class _NTIMediaRollDecorator(_VisibleMixinDecorator):

	@Lazy
	def is_legacy_ipad(self):
		result = is_legacy_uas(self.request, LEGACY_UAS_40)
		return result

	def _decorate_external_impl(self, context, result):
		removal = set()
		items = result[ITEMS]
		# loop through sources
		for idx, item in enumerate(context):
			if IVisible.providedBy(item) and not self._allow_visible(context, item):
				removal.add(idx)
			elif IMediaRef.providedBy(item):
				self._handle_media_ref(items, item, idx)
		# remove disallowed items
		if removal:
			result[ITEMS] = [x for idx, x in enumerate(items) if idx not in removal]

		if self.is_legacy_ipad:
			result[COLLECTION_ITEMS] = result[ITEMS]
			del result[ITEMS]

@component.adapter(INTICourseOverviewGroup)
class _NTICourseOverviewGroupDecorator(_VisibleMixinDecorator):

	@Lazy
	def is_legacy_ipad(self):
		result = is_legacy_uas(self.request, LEGACY_UAS_40)
		return result
	
	def _is_legacy_discussion(self, item):
		nttype = get_type(item.target)
		return nttype in (NTIID_TYPE_COURSE_TOPIC, NTIID_TYPE_COURSE_SECTION_TOPIC)

	def _filter_legacy_discussions(self, context, indexes, removal):
		items = context.Items
		record = self.record(context)
		scope = record.Scope if record is not None else None
		scope = ES_CREDIT if scope == ES_ALL else scope  # map to credit
		m_scope = ENROLLMENT_LINEAGE_MAP.get(scope or u'')
		if not m_scope:
			removal.update(indexes)
		else:
			scopes = {}
			has_credit = False
			for idx in indexes:
				item = items[idx]
				specific = get_specific(item.target)
				scopes[idx] = ES_PUBLIC if OPEN in specific else None
				scopes[idx] = ES_CREDIT if IN_CLASS_SAFE in specific else scopes[idx]
				has_credit = has_credit or scopes[idx] == ES_CREDIT

			m_scope = m_scope[0]  # pick first
			for idx in indexes:
				item = items[idx]
				scope = scopes[idx]
				if not scope:
					removal.add(idx)
				elif m_scope == ES_PUBLIC and scope != ES_PUBLIC:
					removal.add(idx)
				elif m_scope == ES_CREDIT and scope == ES_PUBLIC and has_credit:
					removal.add(idx)

	def _allow_discussion_course_bundle(self, context, item, ext_item):
		record = self.record(context)
		resolved = resolve_discussion_course_bundle(user=self.remoteUser,
													item=item,
													context=context,
												 	record=record)
		if resolved is None:
			return False

		discussion, topic = resolved

		# For legacy purposes we need NTIID to be the id of the topic
		# that the user should see when selecting this resource.
		# As of Dec 2015 all clients are looking at the NTIID field so
		# the resolved topic id has to go there. We need to get clients migrated
		# over to target, which is currently safe to change.  We set target
		# to the course.discussion object and will use a view to resolve it
		# to the specific topic as necessary. This gets these objects exposed for
		# editing while maintaining backwards compatibility.
		ext_item[NTIID] = topic.NTIID
		ext_item['Target-NTIID'] = to_external_ntiid_oid(discussion)
		return True

	def _allow_assessmentref(self, iface, context, item):
		record = self.record(context)
		assg = iface(item, None)
		if assg is None or record is None:
			return False
		if record.Scope == ES_ALL:  # instructor
			return True
		course = record.CourseInstance
		predicate = get_course_assessment_predicate_for_user(self.remoteUser, course)
		result = predicate is not None and predicate(assg)
		return result

	def allow_assignmentref(self, context, item):
		result = self._allow_assessmentref(IQAssignment, context, item)
		return result

	def allow_surveyref(self, context, item):
		result = self._allow_assessmentref(IQSurvey, context, item)
		return result

	def allow_mediaroll(self, ext_item):
		key = COLLECTION_ITEMS if self.is_legacy_ipad else ITEMS
		value  = ext_item.get(key)
		return bool(value)
	
	def _decorate_external_impl(self, context, result):
		idx = 0
		removal = set()
		discussions = []
		items = result[ITEMS]
		# loop through sources
		for idx, item in enumerate(context):
			if IVisible.providedBy(item) and not self._allow_visible(context, item):
				removal.add(idx)
			elif INTIDiscussionRef.providedBy(item):
				if item.isCourseBundle():
					ext_item = items[idx]
					if not self._allow_discussion_course_bundle(context, item, ext_item):
						removal.add(idx)
				elif self._is_legacy_discussion(item):
					discussions.append(idx)
			elif IMediaRef.providedBy(item):
				self._handle_media_ref(items, item, idx)
			elif INTIAssignmentRef.providedBy(item) and not self.allow_assignmentref(context, item):
				removal.add(idx)
			elif INTISurveyRef.providedBy(item) and not self.allow_surveyref(context, item):
				removal.add(idx)
			elif INTIMediaRoll.providedBy(item) and not self.allow_mediaroll(items[idx]):
				removal.add(idx)

		# filter legacy discussions
		if discussions:
			self._filter_legacy_discussions(context, discussions, removal)

		# remove disallowed items
		if removal:
			result[ITEMS] = [x for idx, x in enumerate(items) if idx not in removal]

@component.adapter(INTITimeline, IRequest)
@component.adapter(INTIRelatedWorkRef, IRequest)
@interface.implementer(IExternalMappingDecorator)
class _NTIAbsoluteURLDecorator(AbstractAuthenticatedRequestAwareDecorator):

	@Lazy
	def is_legacy_ipad(self):
		result = is_legacy_uas(self.request, LEGACY_UAS_40)
		return result

	def _predicate(self, context, result):
		result = self._is_authenticated
		return result

	def _do_decorate_external(self, context, result):
		package = None
		library = component.queryUtility(IContentPackageLibrary)
		if library is not None:
			units = get_item_content_units(context)
			# FIXME: pick first content unit avaiable; clients
			# should try to give us context
			paths = library.pathToNTIID(units[0].ntiid) if units else None
			package = paths[0] if paths else None
		if package is not None:
			location = IContentUnitHrefMapper(package.key.bucket).href  # parent
			for name in ('href', 'icon'):
				value = getattr(context, name, None)
				if value and not value.startswith('/') and '://' not in value:
					value = urljoin(location, value)
					if self.is_legacy_ipad:  # for legacy ipad
						value = urljoin(self.request.host_url, value)
					result[name] = value

@interface.implementer(IExternalMappingDecorator)
class _IPADLegacyReferenceDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		result = is_legacy_uas(self.request, LEGACY_UAS_40)
		return result

	def _do_decorate_external(self, context, result_map):
		if INTIAssignmentRef.providedBy(context):
			result_map[CLASS] = 'Assignment'
			result_map[MIMETYPE] = 'application/vnd.nextthought.assessment.assignment'
		elif INTIQuestionSetRef.providedBy(context):
			result_map[CLASS] = 'QuestionSet'
			result_map[MIMETYPE] = 'application/vnd.nextthought.naquestionset'
		elif INTIQuestionRef.providedBy(context):
			result_map[CLASS] = 'Question'
			result_map[MIMETYPE] = 'application/vnd.nextthought.naquestion'
		elif INTIDiscussionRef.providedBy(context):
			result_map[MIMETYPE] = 'application/vnd.nextthought.discussion'

@component.adapter(INTICourseOverviewGroup)
@interface.implementer(IExternalObjectDecorator)
class _OverviewGroupDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		external['accentColor'] = original.color

@interface.implementer(IExternalObjectDecorator)
class _BaseAssetDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		if 'ntiid' in external:
			external[NTIID] = external.pop('ntiid')
		if 'target' in external:
			external[u'Target-NTIID'] = external.pop('target')

@component.adapter(INTIQuestionRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIQuestionRefDecorator(_BaseAssetDecorator):
	pass

@interface.implementer(IExternalObjectDecorator)
class _BaseAssessmentRefDecorator(_BaseAssetDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_BaseAssessmentRefDecorator, self).decorateExternalObject(original, external)
		if 'question_count' in external:
			external[u'question-count'] = str(external.pop('question_count'))

@component.adapter(INTIQuestionSetRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIQuestionSetRefDecorator(_BaseAssessmentRefDecorator):
	pass

@component.adapter(INTISurveyRef)
@interface.implementer(IExternalObjectDecorator)
class _NTISurveyRefDecorator(_BaseAssessmentRefDecorator):
	pass

@component.adapter(INTIAssignmentRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIAssignmentRefDecorator(_BaseAssetDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_NTIAssignmentRefDecorator, self).decorateExternalObject(original, external)
		if 'containerId' in external:
			external[u'ContainerId'] = external.pop('containerId')

@component.adapter(INTIDiscussionRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIDiscussionRefDecorator(_BaseAssetDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_NTIDiscussionRefDecorator, self).decorateExternalObject(original, external)
		if 'target' in external:
			external['Target-NTIID'] = external.pop('target')
		if 'Target-NTIID' in external:
			external[NTIID] = external['Target-NTIID']

@component.adapter(INTIRelatedWorkRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIRelatedWorkRefDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		if 'byline' in external:
			external[u'creator'] = external['byline']  # legacy
		description = external.get('description')
		if description:
			external[u'desc'] = external['description'] = description.strip()  # legacy
		if 'target' in external:
			external[u'target-NTIID'] = external[u'target-ntiid'] = external['target']  # legacy
		if 'type' in external:
			external[u'targetMimeType'] = external['type']

@component.adapter(INTITimeline)
@interface.implementer(IExternalObjectDecorator)
class _NTITimelineDecorator(_BaseAssetDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_NTITimelineDecorator, self).decorateExternalObject(original, external)
		if 'description' in external:
			external[u'desc'] = external['description']
		inline = external.pop('suggested_inline', None)
		if inline is not None:
			external['suggested-inline'] = inline

@interface.implementer(IExternalObjectDecorator)
class _NTIBaseSlideDecorator(_BaseAssetDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_NTIBaseSlideDecorator, self).decorateExternalObject(original, external)
		if 'byline' in external:
			external[u'creator'] = external['byline']
		if CLASS in external:
			external[u'class'] = (external.get(CLASS) or u'').lower()  # legacy
		if 'description' in external and not external['description']:
			external.pop('description')
		external[u'ntiid'] = external[NTIID] = original.ntiid

@component.adapter(INTISlide)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideDecorator(_NTIBaseSlideDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_NTISlideDecorator, self).decorateExternalObject(original, external)
		for name in ("slidevideostart", "slidevideoend", "slidenumber"):
			value = external.get(name)
			if value is not None and not isinstance(value, six.string_types):
				external[name] = str(value)

@component.adapter(INTISlideVideo)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideVideoDecorator(_NTIBaseSlideDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_NTISlideVideoDecorator, self).decorateExternalObject(original, external)
		if 'video_ntiid' in external:
			external[u'video-ntiid'] = external['video_ntiid']  # legacy

@component.adapter(INTISlideDeck)
@interface.implementer(IExternalObjectDecorator)
class _NTISlideDeckDecorator(_NTIBaseSlideDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_NTISlideDeckDecorator, self).decorateExternalObject(original, external)
		external[u'creator'] = original.byline

@component.adapter(INTIAudioRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIAudioRefDecorator(_BaseAssetDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_NTIAudioRefDecorator, self).decorateExternalObject(original, external)
		if MIMETYPE in external:
			external[MIMETYPE] = u"application/vnd.nextthought.ntiaudio"

@component.adapter(INTIVideoRef)
@interface.implementer(IExternalObjectDecorator)
class _NTIVideoRefDecorator(_BaseAssetDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_NTIVideoRefDecorator, self).decorateExternalObject(original, external)
		if MIMETYPE in external:
			external[MIMETYPE] = u"application/vnd.nextthought.ntivideo"

@interface.implementer(IExternalObjectDecorator)
class _BaseMediaDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		if MIMETYPE in external:
			external[StandardExternalFields.CTA_MIMETYPE] = external[MIMETYPE]  # legacy

		if 'byline' in external:
			external[u'creator'] = external['byline']  # legacy

		if 'ntiid' in external and NTIID not in external:
			external[NTIID] = external['ntiid']  # alias

		for name in (u'DCDescription', u'DCTitle'):
			external.pop(name, None)

		for source in external.get('sources') or ():
			source.pop(CREATED_TIME, None)
			source.pop(LAST_MODIFIED, None)

		for transcript in external.get('transcripts') or ():
			transcript.pop(CREATED_TIME, None)
			transcript.pop(LAST_MODIFIED, None)

@component.adapter(INTIVideo)
@interface.implementer(IExternalObjectDecorator)
class _NTIVideoDecorator(_BaseMediaDecorator):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		super(_NTIVideoDecorator, self).decorateExternalObject(original, external)
		if 'closed_caption' in external:
			external[u'closedCaptions'] = external['closed_caption']  # legacy

		for name in ('poster', 'label', 'subtitle'):
			if name in external and not external[name]:
				del external[name]

		title = external.get('title')
		if title and not external.get('label'):
			external['label'] = title

@component.adapter(INTIAudio)
@interface.implementer(IExternalObjectDecorator)
class _NTIAudioDecorator(_BaseMediaDecorator):
	pass
