#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import time

from requests.structures import CaseInsensitiveDict

from zope import component

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary.views.sync_views import _AbstractSyncAllLibrariesView

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.utils import transfer_resources_from_filer

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.contenttypes.presentation.synchronizer import can_be_removed
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.contenttypes.presentation.utils import yield_sync_courses
from nti.app.contenttypes.presentation.utils import remove_presentation_asset

from nti.app.contenttypes.presentation.utils.common import course_assets
from nti.app.contenttypes.presentation.utils.common import remove_all_invalid_assets
from nti.app.contenttypes.presentation.utils.common import remove_course_inaccessible_assets

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.cabinet.filer import DirectoryFiler

from nti.common.string import is_true

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_hierarchy

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import ICoursePresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import remove_transaction_history

from nti.site.interfaces import IHostPolicyFolder

from nti.site.hostpolicy import get_host_site

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


def _get_course_ntiids(values):
    ntiids = values.get('ntiid') or values.get('ntiids')
    if ntiids and isinstance(ntiids, six.string_types):
        ntiids = ntiids.split()
    return ntiids


def _read_input(request):
    result = CaseInsensitiveDict()
    if request:
        if request.body:
            values = read_body_as_external_object(request)
        else:
            values = request.params
        result.update(values)
    return result


@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_NTI_ADMIN,
               name='GetCoursePresentationAssets')
class GetCoursePresentationAssetsView(AbstractAuthenticatedView):

    def _found(self, x):
        ntiid = x.ntiid or u''
        return component.queryUtility(ICoursePresentationAsset, name=ntiid) != None

    def __call__(self):
        total = 0
        params = CaseInsensitiveDict(self.request.params)
        ntiids = _get_course_ntiids(params)
        result = LocatedExternalDict()
        result[ITEMS] = items = {}
        for course in yield_sync_courses(ntiids):
            entry = ICourseCatalogEntry(course)
            container = IPresentationAssetContainer(course)
            items[entry.ntiid] = sorted((x for x in container.values() if self._found(x)),
                                        key=lambda x: x.__class__.__name__)
            total += len(items[entry.ntiid])

        self.request.acl_decoration = False
        result[ITEM_COUNT] = result[TOTAL] = total
        return result


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_NTI_ADMIN,
               name='ResetPresentationAssets')
class ResetPresentationAssetsView(_AbstractSyncAllLibrariesView):

    def _process_course(self, context, force=False):
        catalog = get_library_catalog()
        course = ICourseInstance(context)
        folder = find_interface(course, IHostPolicyFolder, strict=False)
        with current_site(get_host_site(folder.__name__)):
            removed = []
            registry = folder.getSiteManager()

            # remove registered assets
            for name, item, container in course_assets(course):
                provided = iface_of_asset(item)
                registered = component.queryUtility(provided, name)
                if registered is None or can_be_removed(registered, force=force):
                    container.pop(name, None)
                    removed.append(item)
                    remove_presentation_asset(item, registry, catalog,
                                              name=name, event=False)

            # remove last mod keys
            clear_namespace_last_modified(course, catalog)

            # remove all transactions
            for obj in removed:
                remove_transaction_history(obj)

            # only return ntiids
            return [x.ntiid for x in removed]

    def _do_call(self):
        values = self.readInput()
        force = is_true(values.get('force'))
        result = LocatedExternalDict()
        items = result[ITEMS] = self._process_course(self.context, force)
        result[ITEM_COUNT] = result[TOTAL] = len(items)
        return result


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_SYNC_LIBRARY,
               name='SyncPresentationAssets')
class SyncPresentationAssetsView(_AbstractSyncAllLibrariesView):

    def _process_course(self, context):
        course = ICourseInstance(context)
        folder = find_interface(course, IHostPolicyFolder, strict=False)
        with current_site(get_host_site(folder.__name__)):
            synchronize_course_lesson_overview(course)

    def _do_call(self):
        now = time.time()
        result = LocatedExternalDict()
        result['SyncTime'] = time.time() - now
        return result


@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_SYNC_LIBRARY,
               name='RemoveCourseInaccessibleAssets')
class RemoveCourseInaccessibleAssetsView(AbstractAuthenticatedView,
                                         ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        return _read_input(self.request)

    def __call__(self):
        endInteraction()
        try:
            result = remove_course_inaccessible_assets()
        finally:
            restoreInteraction()
        return result


@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_SYNC_LIBRARY,
               name='RemoveInvalidPresentationAssets')
class RemoveInvalidPresentationAssetsView(AbstractAuthenticatedView,
                                          ModeledContentUploadRequestUtilsMixin):

    def __call__(self):
        result = LocatedExternalDict()
        endInteraction()
        try:
            result[ITEMS] = dict(remove_all_invalid_assets())
        finally:
            restoreInteraction()
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IDataserverFolder,
             permission=nauth.ACT_NTI_ADMIN,
             name='OutlineObjectCourseResolver')
class OutlineObjectCourseResolverView(AbstractAuthenticatedView):
    """
    An admin view to fetch the courses associated with a given
    outline object (node/lesson/group/asset), given by an `ntiid`
    param.
    """

    def _possible_courses(self, course):
        return get_course_hierarchy(course)

    def __call__(self):
        result = LocatedExternalDict()
        result[ITEMS] = items = []
        params = CaseInsensitiveDict(self.request.params)
        ntiid = params.get('ntiid')
        obj = find_object_with_ntiid(ntiid)
        course = find_interface(obj, ICourseInstance, strict=False)
        course = ICourseInstance(obj, None) if course is None else course
        if course is not None:
            possible_courses = self._possible_courses(course)
            our_outline = course.Outline
            for course in possible_courses:
                if course.Outline == our_outline:
                    items.append(course)
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        result['Site'] = result['SiteInfo'] = getSite().__name__
        return result


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_NTI_ADMIN,
               name='FixImportCourseReferences')
class FixImportCourseReferences(AbstractAuthenticatedView):
    """
    For imported/synced courses, iterate through and make sure
    any course-file images/refs on disk are synced into course
    structure.
    """

    def _update_assets(self, course, source_filer, course_filer):
        change_count = 0
        for _, item, _ in course_assets(course):
            asset = IConcreteAsset(item, item)
            transfer_result = transfer_resources_from_filer(iface_of_asset(asset),
                                                            asset,
                                                            source_filer,
                                                            course_filer)
            if transfer_result:
                change_count += 1
        return change_count

    def _update_discussions(self, course, source_filer, course_filer):
        change_count = 0
        discussions = ICourseDiscussions(course)
        if discussions is not None:
            for discussion in discussions.values():
                transfer_result = transfer_resources_from_filer(ICourseDiscussion,
                                                                discussion,
                                                                source_filer,
                                                                course_filer)
                if transfer_result:
                    change_count += 1
        return change_count

    def __call__(self):
        result = LocatedExternalDict()
        course = ICourseInstance(self.context)
        course_filer = get_course_filer(course)
        source_filer = DirectoryFiler(course.root.absolute_path)
        disc_change = self._update_discussions(course,
                                               source_filer,
                                               course_filer)
        asset_change = self._update_assets(course,
                                           source_filer,
                                           course_filer)
        result['DiscussionChangeCount'] = disc_change
        result['AssetChangeCount'] = asset_change
        result[ITEM_COUNT] = result[TOTAL] = asset_change + disc_change
        entry_ntiid = ICourseCatalogEntry(course).ntiid
        logger.info('Asset/Discussion refs updated from disk (asset=%s) (discussion=%s) (course=%s)',
                    asset_change, disc_change, entry_ntiid)
        return result
