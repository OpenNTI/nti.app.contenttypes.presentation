#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import copy
from itertools import chain
from urlparse import urlparse
from collections import Mapping

import transaction

from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from zope.event import notify as event_notify

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import get_safe_source_filename
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile import validate_sources

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.processors.mixins import check_exists
from nti.app.contenttypes.presentation.processors.mixins import register_utility

from nti.app.contenttypes.presentation.utils.asset import intid_register
from nti.app.contenttypes.presentation.utils.asset import add_2_connection

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_courses

from nti.app.contenttypes.presentation.views import VIEW_ASSETS

from nti.app.contenttypes.presentation.views.view_mixins import preflight_input
from nti.app.contenttypes.presentation.views.view_mixins import href_safe_to_external_object

from nti.app.contenttypes.presentation.views.view_mixins import PresentationAssetMixin

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.resources.utils import get_course_filer
from nti.app.products.courseware.resources.utils import is_internal_file_link
from nti.app.products.courseware.resources.utils import to_external_file_link
from nti.app.products.courseware.resources.utils import get_file_from_external_link

from nti.appserver.ugd_edit_views import UGDPutView

from nti.assessment.interfaces import IQPoll
from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQInquiry
from nti.assessment.interfaces import IQAssessment
from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.contentfile.interfaces import IContentBaseFile

from nti.contentlibrary.indexed_data import get_site_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.discussions.utils import resolve_discussion_course_bundle

from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation import AUDIO_MIME_TYPES
from nti.contenttypes.presentation import VIDEO_MIME_TYPES
from nti.contenttypes.presentation import POLL_REF_MIME_TYPES
from nti.contenttypes.presentation import TIMELINE_MIME_TYPES
from nti.contenttypes.presentation import SURVEY_REF_MIME_TYPES
from nti.contenttypes.presentation import TIMELINE_REF_MIME_TYPES
from nti.contenttypes.presentation import ASSIGNMENT_REF_MIME_TYPES
from nti.contenttypes.presentation import SLIDE_DECK_REF_MIME_TYPES
from nti.contenttypes.presentation import QUESTIONSET_REF_MIME_TYPES
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import COURSE_OVERVIEW_GROUP_MIME_TYPES
from nti.contenttypes.presentation import RELATED_WORK_REF_POINTER_MIME_TYPES

from nti.contenttypes.presentation.discussion import is_nti_course_bundle

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIAudioRoll
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import INTIVideoRoll
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTIInquiryRef
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import ICoursePresentationAsset
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.interfaces import PresentationAssetCreatedEvent
from nti.contenttypes.presentation.interfaces import WillUpdatePresentationAssetEvent

from nti.contenttypes.presentation.internalization import internalization_ntiaudioref_pre_hook
from nti.contenttypes.presentation.internalization import internalization_ntivideoref_pre_hook

from nti.contenttypes.presentation.utils import create_from_external
from nti.contenttypes.presentation.utils import get_external_pre_hook

from nti.coremetadata.utils import current_principal

from nti.dataserver import authorization as nauth

from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.externalization.externalization import StandardExternalFields

from nti.externalization.internalization import notify_modified

from nti.externalization.oids import to_external_ntiid_oid

from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE


def principalId():
    try:
        return current_principal(False).id
    except AttributeError:
        return None


def notify_created(item, principal=None, externalValue=None):
    add_2_connection(item)  # required
    principal = principal or principalId()  # always get a principal
    event_notify(PresentationAssetCreatedEvent(item, principal, externalValue))
    if IPublishable.providedBy(item) and item.is_published():
        item.unpublish(event=False)


def handle_multipart(context, user, contentObject, sources, provided=None):
    filer = get_course_filer(context, user)
    provided = iface_of_asset(contentObject) if provided is None else provided
    for name, source in sources.items():
        if name in provided:
            # remove existing
            location = getattr(contentObject, name, None)
            if location and is_internal_file_link(location):
                filer.remove(location)
            # save a in a new file
            key = get_safe_source_filename(source, name)
            location = filer.save(key, source,
                                  overwrite=False,
                                  structure=True,
                                  context=contentObject)
            setattr(contentObject, name, location)


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

    def handle_asset(self, item, creator=None):
        proc = IPresentationAssetProcessor(item)
        proc.handle(item, self._course, creator, self.request)
        return item

    def remove_ntiids(self, ext_obj, do_remove):
        if do_remove:
            ext_obj.pop('ntiid', None)
            ext_obj.pop(NTIID, None)

    def readInput(self, no_ntiids=True):
        result = super(PresentationAssetSubmitViewMixin, self).readInput()
        self._remove_ntiids(result, no_ntiids)
        return result

    def transformOutput(self, obj):
        provided = iface_of_asset(obj)
        if provided is not None and 'href' in provided:
            result = href_safe_to_external_object(obj)
        else:
            result = obj
        return result


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
        self.handle_asset(contentObject, creator)
        
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

# # put views
#
# @view_config(context=IPresentationAsset)
# @view_defaults(route_name='objects.generic.traversal',
#                renderer='rest',
#                request_method='PUT',
#                permission=nauth.ACT_CONTENT_EDIT)
# class PresentationAssetPutView(PresentationAssetSubmitViewMixin,
#                                UGDPutView):  # order matters
#
#     def preflight(self, contentObject, externalValue):
#         preflight_input(externalValue, self.request)
#
#     def postflight(self, updatedObject, externalValue, preflight=None):
#         return None
#
#     def updateContentObject(self, contentObject, externalValue, set_id=False, notify=True):
#         data = self.preflight(contentObject, externalValue)
#         originalSource = copy.deepcopy(externalValue)
#         pre_hook = get_external_pre_hook(externalValue)
#
#         event_notify(WillUpdatePresentationAssetEvent(contentObject,
#                                                       self.remoteUser,
#                                                       externalValue))
#
#         result = UGDPutView.updateContentObject(self,
#                                                 contentObject,
#                                                 externalValue,
#                                                 set_id=set_id,
#                                                 notify=False,
#                                                 pre_hook=pre_hook)
#         sources = get_all_sources(self.request)
#         if sources:
#             courses = get_presentation_asset_courses(self.context) or (self._course,)
#             validate_sources(self.remoteUser, result, sources)
#             _handle_multipart(next(iter(courses)),
#                               self.remoteUser,
#                               self.context,
#                               sources)
#
#         self.postflight(contentObject, externalValue, data)
#         notify_modified(contentObject, originalSource)
#         return result
#
#     def _get_containers(self):
#         result = []
#         for iface in (INTICourseOverviewGroup, INTILessonOverview):
#             parent = find_interface(self.context, iface, strict=False)
#             if parent is not None:
#                 result.append(parent)
#         return result
#
#     def __call__(self):
#         result = UGDPutView.__call__(self)
#         containers = self._get_containers()
#         self._handle_asset(iface_of_asset(result), result,
#                            result.creator, containers)
#         return self.transformOutput(result)
#
# @view_config(context=IPackagePresentationAsset)
# @view_defaults(route_name='objects.generic.traversal',
#                renderer='rest',
#                request_method='PUT',
#                permission=nauth.ACT_CONTENT_EDIT)
# class PackagePresentationAssetPutView(PresentationAssetPutView):
#
#     @Lazy
#     def _site_name(self):
#         folder = find_interface(self.context, IHostPolicyFolder, strict=False)
#         if folder is None:
#             result = super(PackagePresentationAssetPutView, self)._site_name
#         else:
#             result = folder.__name__
#         return result
#
#     @Lazy
#     def _course(self):
#         result = find_interface(self.context, ICourseInstance, strict=False)
#         if result is not None:  # direct check in case course w/ no pkg
#             return result
#         package = find_interface(self.context, IContentPackage, strict=False)
#         if package is not None:
#             sites = get_component_hierarchy_names()  # check sites
#             courses = get_courses_for_packages(sites, package.ntiid)
#             result = courses[0] if courses else None  # should always find one
#         return result
#
# @view_config(context=ICoursePresentationAsset)
# @view_defaults(route_name='objects.generic.traversal',
#                renderer='rest',
#                request_method='PUT',
#                permission=nauth.ACT_CONTENT_EDIT)
# class CoursePresentationAssetPutView(PresentationAssetPutView):
#
#     @Lazy
#     def _site_name(self):
#         folder = find_interface(self.context, IHostPolicyFolder, strict=False)
#         return folder.__name__
#
#     @Lazy
#     def _course(self):
#         course = find_interface(self.context, ICourseInstance, strict=False)
#         return course
