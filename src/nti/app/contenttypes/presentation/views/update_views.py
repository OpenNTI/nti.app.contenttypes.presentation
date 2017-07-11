#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import copy

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

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_courses

from nti.app.contenttypes.presentation.views import VIEW_ASSETS

from nti.app.contenttypes.presentation.views.view_mixins import preflight_input
from nti.app.contenttypes.presentation.views.view_mixins import href_safe_to_external_object

from nti.app.contenttypes.presentation.views.view_mixins import PresentationAssetMixin

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.ugd_edit_views import UGDPutView

from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.contenttypes.presentation.interfaces import WillUpdatePresentationAssetEvent

from nti.contenttypes.presentation.utils import create_from_external
from nti.contenttypes.presentation.utils import get_external_pre_hook

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import StandardExternalFields

from nti.externalization.internalization import notify_modified

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
        self._remove_ntiids(result, no_ntiids)
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
            handle_multipart(next(iter(courses)), # pick first
                             self.remoteUser,
                             self.context,
                             sources)
        # post process and notify
        self.postflight(contentObject, externalValue, data)
        notify_modified(contentObject, originalSource)
        return result

    def __call__(self):
        result = UGDPutView.__call__(self)
        self.handle_asset(result, self.remoteUser)
        return self.transformOutput(result)
