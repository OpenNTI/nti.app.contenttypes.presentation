#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import copy
from collections import Mapping

import transaction

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from zope.event import notify as event_notify

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile import validate_sources

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.processors.mixins import check_exists
from nti.app.contenttypes.presentation.processors.mixins import notify_created
from nti.app.contenttypes.presentation.processors.mixins import handle_multipart
from nti.app.contenttypes.presentation.processors.mixins import register_utility

from nti.app.contenttypes.presentation.utils.asset import intid_register
from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_courses

from nti.app.contenttypes.presentation.views import VIEW_ASSETS
from nti.app.contenttypes.presentation.views import VIEW_CONTENTS

from nti.app.contenttypes.presentation.views.view_mixins import preflight_input
from nti.app.contenttypes.presentation.views.view_mixins import preflight_mediaroll
from nti.app.contenttypes.presentation.views.view_mixins import preflight_overview_group
from nti.app.contenttypes.presentation.views.view_mixins import preflight_lesson_overview
from nti.app.contenttypes.presentation.views.view_mixins import href_safe_to_external_object

from nti.app.contenttypes.presentation.views.view_mixins import PresentationAssetMixin

from nti.app.products.courseware.views.view_mixins import IndexedRequestMixin

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.ugd_edit_views import UGDPutView

from nti.assessment.interfaces import IQPoll
from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation import POLL_REF_MIME_TYPES
from nti.contenttypes.presentation import SURVEY_REF_MIME_TYPES
from nti.contenttypes.presentation import TIMELINE_REF_MIME_TYPES
from nti.contenttypes.presentation import ASSIGNMENT_REF_MIME_TYPES
from nti.contenttypes.presentation import SLIDE_DECK_REF_MIME_TYPES
from nti.contenttypes.presentation import QUESTIONSET_REF_MIME_TYPES
from nti.contenttypes.presentation import COURSE_OVERVIEW_GROUP_MIME_TYPES
from nti.contenttypes.presentation import RELATED_WORK_REF_POINTER_MIME_TYPES

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer

from nti.contenttypes.presentation.interfaces import WillUpdatePresentationAssetEvent

from nti.contenttypes.presentation.internalization import internalization_ntiaudioref_pre_hook
from nti.contenttypes.presentation.internalization import internalization_ntivideoref_pre_hook

from nti.contenttypes.presentation.utils import is_media_mimeType
from nti.contenttypes.presentation.utils import create_from_external
from nti.contenttypes.presentation.utils import is_timeline_mimeType
from nti.contenttypes.presentation.utils import get_external_pre_hook

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import StandardExternalFields

from nti.externalization.internalization import notify_modified

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE


class PresentationAssetSubmitViewMixin(PresentationAssetMixin,
                                       AbstractAuthenticatedView):

    @Lazy
    def container(self):
        result = find_interface(self.context, ICourseInstance, strict=False) \
            or find_interface(self.context, IContentPackage, strict=False)
        return result

    @Lazy
    def site(self):
        if self.container is None:
            result = getSite()
        else:
            result = IHostPolicyFolder(self.container)
        return result

    @Lazy
    def registry(self):
        return self.site.getSiteManager()

    @Lazy
    def course(self):
        return ICourseInstance(self.container, None)

    @Lazy
    def entry(self):
        return ICourseCatalogEntry(self.course, None)

    def handle_asset(self, item, creator=None, container=None):
        proc = IPresentationAssetProcessor(item)
        container = container if container is not None else self.container
        proc.handle(item, container, creator, self.request)
        return item

    def remove_ntiids(self, ext_obj, do_remove):
        if do_remove:
            ext_obj.pop('ntiid', None)
            ext_obj.pop(NTIID, None)

    def readInput(self, no_ntiids=True):
        result = super(PresentationAssetSubmitViewMixin, self).readInput()
        self.remove_ntiids(result, no_ntiids)
        return result

    def transformOutput(self, obj):
        provided = iface_of_asset(obj)
        if provided is not None and 'href' in provided:
            result = href_safe_to_external_object(obj)
        else:
            result = obj
        return result


@view_config(context=IContentPackage)
@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_ASSETS,
               request_method='POST',
               permission=nauth.ACT_CONTENT_EDIT)
class PresentationAssetPostView(PresentationAssetSubmitViewMixin,
                                ModeledContentUploadRequestUtilsMixin):  # order matters

    content_predicate = IPresentationAsset.providedBy

    def checkContentObject(self, contentObject, externalValue):
        if contentObject is None or not self.content_predicate(contentObject):
            transaction.doom()
            logger.debug("Failing to POST: input of unsupported/missing Class: %s => %s",
                         externalValue, contentObject)
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Unsupported/missing Class.'),
                             },
                             None)
        return contentObject

    def parseInput(self, externalValue=None):
        # process input
        externalValue = self.readInput() if not externalValue else externalValue
        externalValue = preflight_input(externalValue, self.request)
        result = copy.deepcopy(externalValue)  # return original input
        # create and validate
        contentObject = create_from_external(externalValue, notify=False)
        contentObject = self.checkContentObject(contentObject, externalValue)
        # update with external
        self.updateContentObject(contentObject, externalValue,
                                 set_id=True, notify=False)
        return contentObject, result

    def readCreateUpdateContentObject(self, externalValue=None):
        contentObject, externalValue = self.parseInput(externalValue)
        sources = get_all_sources(self.request)
        return contentObject, externalValue, sources

    def _do_call(self):
        creator = self.remoteUser
        contentObject, externalValue, sources = self.readCreateUpdateContentObject()
        contentObject.creator = creator.username  # use string
        provided = iface_of_asset(contentObject)

        # check item does not exists
        check_exists(contentObject, self.registry, self.request, self._extra)

        # process asset
        self.handle_asset(contentObject, creator,)

        # add to connection and register
        intid_register(contentObject, registry=self._registry)
        register_utility(self.registry, contentObject,
                         provided, contentObject.ntiid)

        # handle multi-part data
        if sources:
            validate_sources(self.remoteUser, contentObject, sources)
            handle_multipart(self.container, self.remoteUser,
                             contentObject, sources)

        # notify when object is ready
        notify_created(contentObject, self.remoteUser.username, externalValue)

        # return
        self.request.response.status_int = 201
        return self.transformOutput(contentObject)


# PUT views


@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class PresentationAssetPutView(PresentationAssetSubmitViewMixin,
                               UGDPutView):  # order matters

    def preflight(self, contentObject, externalValue):
        preflight_input(externalValue, self.request)

    def postflight(self, *args, **kwargs):
        return None

    def updateContentObject(self, contentObject, externalValue, set_id=False, notify=False):
        data = self.preflight(contentObject, externalValue)
        originalSource = copy.deepcopy(externalValue)
        pre_hook = get_external_pre_hook(externalValue)
        # notify we are about to update asset
        args = (contentObject, self.remoteUser, externalValue)
        event_notify(WillUpdatePresentationAssetEvent(*args))
        # update asset
        result = UGDPutView.updateContentObject(self,
                                                contentObject,
                                                externalValue,
                                                set_id=set_id,
                                                notify=notify,
                                                pre_hook=pre_hook)
        # check any multipart upload
        sources = get_all_sources(self.request)
        if sources:
            if self.container is None:
                courses = get_presentation_asset_courses(self.context)
            else:
                courses = (self.container,)
            validate_sources(self.remoteUser, result, sources)
            handle_multipart(next(iter(courses)),  # pick first
                             self.remoteUser,
                             self.context,
                             sources)
        # post process
        self.postflight(contentObject, externalValue, data)
        # handle asset in processor
        self.handle_asset(result, self.remoteUser)
        # notify
        notify_modified(contentObject, originalSource)
        return result

    def __call__(self):
        result = UGDPutView.__call__(self)
        return self.transformOutput(result)


@view_config(context=INTILessonOverview)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class LessonOverviewPutView(PresentationAssetPutView):

    def preflight(self, contentObject, externalValue):
        preflight_lesson_overview(externalValue, self.request)
        return {x.ntiid: x for x in contentObject}  # save groups

    def postflight(self, contentObject, externalValue, preflight):
        updated = {x.ntiid for x in contentObject}
        for ntiid, group in preflight.items():
            if ntiid not in updated:  # group removed
                remove_presentation_asset(group, self.registry, self._catalog)


@view_config(context=INTICourseOverviewGroup)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class CourseOverviewGroupPutView(PresentationAssetPutView):

    def preflight(self, contentObject, externalValue):
        preflight_overview_group(externalValue, self.request)
        return {x.ntiid: x for x in contentObject}

    def postflight(self, contentObject, externalValue, preflight):
        updated = {x.ntiid for x in contentObject}
        for ntiid, item in preflight.items():
            if ntiid not in updated:  # ref removed
                remove_presentation_asset(item, self.registry, self._catalog)


@view_config(context=INTIMediaRoll)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class MediaRollPutView(PresentationAssetPutView):

    def preflight(self, contentObject, externalValue):
        preflight_mediaroll(externalValue, self.request)
        return {x.ntiid: x for x in contentObject}

    def postflight(self, contentObject, externalValue, preflight):
        updated = {x.ntiid for x in contentObject}
        for ntiid, item in preflight.items():
            if ntiid not in updated:  # ref removed
                remove_presentation_asset(item, self.registry, self._catalog)


@view_config(context=INTILessonOverview)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name=VIEW_CONTENTS,
               permission=nauth.ACT_CONTENT_EDIT)
class LessonOverviewOrderedContentsView(PresentationAssetSubmitViewMixin,
                                        ModeledContentUploadRequestUtilsMixin,
                                        IndexedRequestMixin):  # order matters

    content_predicate = INTICourseOverviewGroup.providedBy

    def checkContentObject(self, contentObject, externalValue):
        if contentObject is None or not self.content_predicate(contentObject):
            transaction.doom()
            logger.debug("Failing to POST: input of unsupported/missing Class: %s => %s",
                         externalValue, contentObject)
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Unsupported/missing Class.'),
                             },
                             None)
        return contentObject

    def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
        # process input
        externalValue = self.readInput() if not externalValue else externalValue
        if MIMETYPE not in externalValue:
            externalValue[MIMETYPE] = COURSE_OVERVIEW_GROUP_MIME_TYPES[0]
        externalValue = preflight_input(externalValue, self.request)
        result = copy.deepcopy(externalValue)  # return original input
        # create object
        contentObject = create_from_external(externalValue, notify=False)
        contentObject = self.checkContentObject(contentObject, externalValue)
        return contentObject, result

    def _do_call(self):
        index = self._get_index()
        creator = self.remoteUser
        contentObject, external = self.readCreateUpdateContentObject(creator)

        # take ownership
        contentObject.__parent__ = self.context

        # check item does not exists and notify
        check_exists(contentObject, self.registry, self.request, self.extra)

        # handle asset in processor
        self.handle_asset(contentObject, self.remoteUser)

        # add to connection and register
        intid_register(contentObject, registry=self._registry)
        register_utility(self.registry, contentObject,
                         INTICourseOverviewGroup, contentObject.ntiid)

        # notify when object is ready
        notify_created(contentObject, self.remoteUser.username, external)

        # insert in context, lock and notify
        self.context.insert(index, contentObject)
        self.context.childOrderLock()
        notify_modified(self.context, external, external_keys=(ITEMS,))

        # return
        self.request.response.status_int = 201
        return contentObject


@view_config(context=INTICourseOverviewGroup)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name=VIEW_CONTENTS,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseOverviewGroupInsertView(PresentationAssetSubmitViewMixin,
                                    ModeledContentUploadRequestUtilsMixin,
                                    IndexedRequestMixin):  # order matters
    """
    We accept asset items by index here. We handle two types specially here:

    We turn media, timeline, and slidedecks into refs here, given an NTIID.
    """

    content_predicate = IGroupOverViewable.providedBy

    def remove_ntiids(self, ext_obj, do_remove):
        # Do not remove our media ntiids, these will be our ref targets.
        # If we don't have a mimeType, we need the ntiid to fetch the (video)
        # object.
        mimeType = ext_obj.get(MIMETYPE) or ext_obj.get('mimeType')
        if mimeType and not is_media_mimeType(mimeType) and not is_timeline_mimeType(mimeType):
            super(CourseOverviewGroupInsertView, self).remove_ntiids(ext_obj, do_remove)

    def _overviewable_mimeType(self, obj):
        if INTISlideDeck.providedBy(obj) or INTISlideDeckRef.providedBy(obj):
            result = SLIDE_DECK_REF_MIME_TYPES[0]
        # timelines
        elif INTITimeline.providedBy(obj) or INTITimelineRef.providedBy(obj):
            result = TIMELINE_REF_MIME_TYPES[0]
        # relatedwork refs
        elif INTIRelatedWorkRef.providedBy(obj) or INTIRelatedWorkRefPointer.providedBy(obj):
            result = RELATED_WORK_REF_POINTER_MIME_TYPES[0]
        # media objects
        elif INTIMedia.providedBy(obj) or INTIMediaRef.providedBy(obj):
            result = obj.mimeType
        # assignment objects
        elif IQAssignment.providedBy(obj) or INTIAssignmentRef.providedBy(obj):
            result = ASSIGNMENT_REF_MIME_TYPES[0]
        # poll objects
        elif IQPoll.providedBy(obj) or INTIPollRef.providedBy(obj):
            result = POLL_REF_MIME_TYPES[0]
        # survey objects
        elif IQSurvey.providedBy(obj) or INTISurveyRef.providedBy(obj):
            result = SURVEY_REF_MIME_TYPES[0]
        # question sets
        elif IQuestionSet.providedBy(obj) or INTIQuestionSetRef.providedBy(obj):
            result = QUESTIONSET_REF_MIME_TYPES[0]
        else:
            result = None
        return result

    def _do_preflight_input(self, externalValue):
        """
        Swizzle media into refs for overview groups. If we're missing a mimetype, the given
        ntiid *must* resolve to a video/timeline. All other types should be fully defined (ref) objects.
        """
        if isinstance(externalValue, Mapping) and MIMETYPE not in externalValue:
            ntiid = externalValue.get('ntiid') or externalValue.get(NTIID)
            if not ntiid:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u'Missing overview group item NTIID.'),
                                 },
                                 None)

            resolved = find_object_with_ntiid(ntiid)
            if resolved is None:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u'Missing overview group item.'),
                                 },
                                 None)

            mimeType = self._overviewable_mimeType(resolved)
            if not mimeType:
                # We did not have a mimetype, and we have an ntiid the resolved
                # into an unexpected type; blow chunks.
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u'Invalid overview group item.'),
                                 },
                                 None)

        if isinstance(externalValue, Mapping):
            mimeType = externalValue.get(MIMETYPE) or externalValue.get('mimeType')
            if is_media_mimeType(mimeType):
                internalization_ntiaudioref_pre_hook(None, externalValue)
                internalization_ntivideoref_pre_hook(None, externalValue)
        return preflight_input(externalValue, self.request)

    def checkContentObject(self, contentObject, externalValue):
        if contentObject is None or not self.content_predicate(contentObject):
            transaction.doom()
            logger.debug("Failing to POST: input of unsupported/missing Class: %s => %s",
                         externalValue, contentObject)
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Unsupported/missing Class.'),
                             },
                             None)
        return contentObject

    def parseInput(self, creator, search_owner=False, externalValue=None):
        external_input = self.readInput() if not externalValue else externalValue
        externalValue = self._do_preflight_input(external_input)
        external_input = copy.deepcopy(external_input)  # return original input
        if isinstance(externalValue, Mapping):
            contentObject = create_from_external(externalValue, notify=False)
            contentObject = self.checkContentObject(
                contentObject, externalValue)
        else:
            contentObject = externalValue
        return contentObject, external_input

    def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
        contentObject, externalValue = self.parseInput(
            creator, search_owner, externalValue)
        return contentObject, externalValue

    def _finish_creating_object(self, obj, creator, provided, externalValue):
        """
        Finish creating our object by firing events, registering, etc.
        """
        register_utility(self.registry, obj, provided, obj.ntiid)
        self.handle_asset(obj, creator)
        notify_created(obj, creator, externalValue)

    def _convert_timeline_to_timelineref(self, timeline, creator, externalValue):
        """
        Convert and create a timeline ref that can be stored in our overview group.
        """
        timeline_ref = INTITimelineRef(timeline)
        self._finish_creating_object(timeline_ref, 
                                     creator, 
                                     INTITimelineRef, 
                                     externalValue)
        return timeline_ref

    def _convert_relatedwork_to_pointer(self, relatedwork, creator, externalValue):
        """
        Convert and create a relatedwork ref that can be stored in our overview group.
        """
        asset_ref = INTIRelatedWorkRefPointer(relatedwork)
        self._finish_creating_object(asset_ref, 
                                     creator, 
                                     INTIRelatedWorkRefPointer, 
                                     externalValue)
        return asset_ref

    def _do_call(self):
        index = self._get_index()
        creator = self.remoteUser
        contentObject, externalValue = self.readCreateUpdateContentObject(creator)
        provided = iface_of_asset(contentObject)

        # check item does not exists
        check_exists(contentObject, self.registry, self.request, self.extra)
        self._finish_creating_object(contentObject, 
                                     creator, 
                                     provided,
                                     externalValue)

        # save reference
        result = contentObject

        if INTITimeline.providedBy(contentObject):
            result = self._convert_timeline_to_timelineref(result, 
                                                           creator, 
                                                           externalValue)
        elif INTIRelatedWorkRef.providedBy(contentObject):
            result = self._convert_relatedwork_to_pointer(result, 
                                                          creator, 
                                                          externalValue)

        # insert in group
        self.context.insert(index, result)

        # intid registration
        intid_register(result, registry=self.registry)
        if result is not contentObject:
            # set lineage
            parent = self.container if self.container is not None else self.context
            contentObject.__parent__ = parent
            intid_register(contentObject, registry=self.registry)

        # Multi-part data must be done after the object has been registered
        # with the intid facility. Use original object
        sources = get_all_sources(self.request)
        if sources:  # multi-part data
            validate_sources(self.remoteUser, contentObject, sources)
            handle_multipart(self.container, self.remoteUser,
                             contentObject, sources)

        # notify and lock
        notify_modified(self.context, externalValue, external_keys=(ITEMS,))
        self.request.response.status_int = 201
        self.context.childOrderLock()

        # We don't return refs in the overview group; so don't here either.
        result = IConcreteAsset(result, result)
        return self.transformOutput(result)
