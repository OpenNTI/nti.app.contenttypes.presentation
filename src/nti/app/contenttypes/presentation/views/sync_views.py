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

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary.views.sync_views import _AbstractSyncAllLibrariesView

from nti.app.contenttypes.presentation.synchronizer import can_be_removed
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.app.contenttypes.presentation.utils.common import course_assets
from nti.app.contenttypes.presentation.utils.common import remove_all_invalid_assets
from nti.app.contenttypes.presentation.utils.common import fix_all_inaccessible_assets
from nti.app.contenttypes.presentation.utils.common import remove_course_inaccessible_assets

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.common.string import is_true

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import iface_of_asset

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.recorder.record import remove_transaction_history

from nti.site.interfaces import IHostPolicyFolder

from nti.site.hostpolicy import get_host_site

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


@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_SYNC_LIBRARY,
               name='FixInaccessiblePresentationAssets')
class FixInaccessiblePresentationAssetsView(_AbstractSyncAllLibrariesView):

    def _do_call(self):
        result = LocatedExternalDict()
        endInteraction()
        try:
            result[ITEMS] = dict(fix_all_inaccessible_assets())
        finally:
            restoreInteraction()
        return result
