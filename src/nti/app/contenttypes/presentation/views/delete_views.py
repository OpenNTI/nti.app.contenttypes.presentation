#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
from nti.app.contenttypes.presentation.utils.asset import get_component_registry
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from requests.structures import CaseInsensitiveDict

from zope.cachedescriptors.property import Lazy

from zope.event import notify as event_notify

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.app.contenttypes.presentation.views import VIEW_CONTENTS
from nti.app.contenttypes.presentation.views import VIEW_LESSON_REMOVE_REFS

from nti.app.contenttypes.presentation.views.view_mixins import PresentationAssetMixin

from nti.app.externalization.error import raise_json_error

from nti.app.products.courseware.views.view_mixins import DeleteChildViewMixin

from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.contenttypes.presentation.interfaces import ItemRemovedFromItemAssetContainerEvent

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import StandardExternalFields

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE


@view_config(context=IPresentationAsset)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_CONTENT_EDIT)
class PresentationAssetDeleteView(PresentationAssetMixin, UGDDeleteView):

    event = True

    @Lazy
    def _registry(self):
        provided = iface_of_asset(self.context)
        return get_component_registry(self.context, provided)

    def _do_delete_object(self, theObject):
        remove_presentation_asset(theObject,
                                  self._registry,
                                  self._catalog,
                                  event=self.event)
        return theObject


@view_config(context=INTICourseOverviewGroup)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_CONTENT_EDIT)
class CourseOverviewGroupDeleteView(PresentationAssetDeleteView):

    event = True

    def _do_delete_object(self, theObject):
        # remove children first
        for asset in theObject:
            remove_presentation_asset(asset,
                                      self._registry,
                                      self._catalog,
                                      event=False)
        # ready to remove
        remove_presentation_asset(theObject,
                                  self._registry,
                                  self._catalog,
                                  event=self.event)
        return theObject


@view_config(context=INTILessonOverview)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_CONTENT_EDIT)
class LessonOverviewDeleteView(PresentationAssetDeleteView):
    event = False


@view_config(context=INTILessonOverview)
@view_config(context=INTICourseOverviewGroup)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_CONTENTS,
               request_method='DELETE',
               permission=nauth.ACT_CONTENT_EDIT)
class AssetDeleteChildView(AbstractAuthenticatedView, DeleteChildViewMixin):
    """
    A view to delete a child underneath the given context.

    index
            This param will be used to indicate which object should be
            deleted. If the object described by `ntiid` is no longer at
            this index, the object will still be deleted, as long as it
            is unambiguous.

    :raises HTTPConflict if state (index of object) has changed out
    from underneath user
    """

    @Lazy
    def _registry(self):
        folder = find_interface(self.context, IHostPolicyFolder, strict=False)
        return folder.getSiteManager() if folder is not None else None

    def _is_target(self, obj, ntiid):
        return ntiid == getattr(obj, 'target', '') \
            or ntiid == getattr(obj, 'ntiid', '')

    def _remove(self, item, index):
        # We remove the item from our context and clean it
        # up. We want to make sure we clean up the underlying asset.
        # Safe if already gone.
        if item is not None:
            self.context.remove(item)
            # remove concrete to avoid leaks
            concrete = IConcreteAsset(item, item)
            if      concrete is not item \
                    and not INTIVideo.providedBy(concrete) \
                    and IUserCreatedAsset.providedBy(concrete) \
                    and not IContentBackedPresentationAsset.providedBy(concrete):
                remove_presentation_asset(concrete, self._registry)
        else:
            item = self.context.pop(index)
        # remove
        remove_presentation_asset(item, self._registry)
        # broadcast container removal
        event = ItemRemovedFromItemAssetContainerEvent(self.context, item)
        event_notify(event)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             name=VIEW_LESSON_REMOVE_REFS,
             context=INTILessonOverview,
             request_method='DELETE',
             permission=nauth.ACT_CONTENT_EDIT)
class RemoveRefsView(AbstractAuthenticatedView):
    """
    Remove all refs underneath a lesson pointing at a given ntiid.

    target
            The ref target that will be used to find out which refs to
            remove.
    """

    @Lazy
    def _registry(self):
        folder = find_interface(self.context, IHostPolicyFolder, strict=False)
        return folder.getSiteManager() if folder is not None else None

    def _is_target(self, obj, ntiid):
        concrete = IConcreteAsset(obj, obj)
        return ntiid == getattr(obj, 'target', '') \
            or ntiid == getattr(concrete, 'target', '')

    def _remove_from_group(self, item, group):
        # We remove the item from our context and clean it
        # up. We want to make sure we clean up the underlying asset.
        # Safe if already gone.
        group.remove(item)
        # remove concrete to avoid leaks
        concrete = IConcreteAsset(item, item)
        if      concrete is not item \
                and IUserCreatedAsset.providedBy(concrete) \
                and not IContentBackedPresentationAsset.providedBy(concrete):
            remove_presentation_asset(concrete, self._registry)
        # remove
        remove_presentation_asset(item, self._registry)
        # broadcast container removal
        event_notify(ItemRemovedFromItemAssetContainerEvent(group, item))
        group.childOrderLock()

    def _get_target_ntiid(self):
        values = CaseInsensitiveDict(self.request.params)
        target_ntiid = values.get('target') \
            or values.get('target_ntiid') \
            or values.get('ntiid')
        return target_ntiid

    def __call__(self):
        count = 0
        target_ntiid = self._get_target_ntiid()

        if target_ntiid is None:
            msg = _(u'No target NTIID given for reference removal.')
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': msg,
                                 'code': 'NoTargetNTIID'
                             },
                             None)

        for group in self.context.Items or ():
            for item in list(group) or ():
                if self._is_target(item, target_ntiid):
                    self._remove_from_group(item, group)
                    count += 1

        logger.info('%s refs removed from %s (target=%s)',
                    count, self.context.ntiid, target_ntiid)
        return hexc.HTTPOk()
