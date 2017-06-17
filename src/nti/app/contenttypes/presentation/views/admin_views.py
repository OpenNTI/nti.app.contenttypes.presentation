#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time

from zope import component

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary.views.sync_views import _AbstractSyncAllLibrariesView

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.utils import transfer_resources_from_filer

from nti.app.contenttypes.presentation.synchronizer import can_be_removed
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

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

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.index import get_assets_catalog

from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.recorder.record import remove_transaction_history

from nti.site.interfaces import IHostPolicyFolder

from nti.site.hostpolicy import get_host_site
from nti.site.hostpolicy import get_all_host_sites

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


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
            return synchronize_course_lesson_overview(course)

    def _do_call(self):
        now = time.time()
        result = LocatedExternalDict()
        items = result[ITEMS] = self._process_course(self.context)
        result[ITEM_COUNT] = result[TOTAL] = len(items)
        result['SyncTime'] = time.time() - now
        return result


@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_SYNC_LIBRARY,
               name='RemoveCourseInaccessibleAssets')
class RemoveCourseInaccessibleAssetsView(AbstractAuthenticatedView):

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
class RemoveInvalidPresentationAssetsView(_AbstractSyncAllLibrariesView):

    def _do_call(self):
        result = LocatedExternalDict()
        endInteraction()
        try:
            result[ITEMS] = dict(remove_all_invalid_assets())
        finally:
            restoreInteraction()
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             permission=nauth.ACT_NTI_ADMIN,
             context=IDataserverFolder,
             name='RebuildPresentationAssetCatalog')
class RebuildEvaluationCatalogView(AbstractAuthenticatedView):

    def __call__(self):
        intids = component.getUtility(IIntIds)
        # clear indexes
        catalog = get_assets_catalog()
        for index in list(catalog.values()):
            index.clear()
        # reindex
        seen = set()
        for host_site in get_all_host_sites():  # check all sites
            logger.info("Processing site %s", host_site.__name__)
            with current_site(host_site):
                for _, evaluation in list(component.getUtilitiesFor(IPresentationAsset)):
                    doc_id = intids.queryId(evaluation)
                    if doc_id is None or doc_id in seen:
                        continue
                    seen.add(doc_id)
                    catalog.index_doc(doc_id, evaluation)
        result = LocatedExternalDict()
        result[ITEM_COUNT] = result[TOTAL] = len(seen)
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
