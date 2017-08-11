#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import site as current_site

from zope.security.interfaces import IPrincipal

from nti.app.authentication import get_remote_user

from nti.app.contenttypes.presentation.utils.asset import check_docket_targets

from nti.app.contenttypes.presentation.synchronizer import clear_course_assets
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import remove_and_unindex_course_assets
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.utils import transfer_resources_from_filer

from nti.cabinet.filer import transfer_to_native_file

from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.courses.importer import BaseSectionImporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSectionImporter

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import interface_of_asset

from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import IItemAssetContainer
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.coremetadata.utils import current_principal

from nti.site.interfaces import IHostPolicyFolder


@interface.implementer(ICourseSectionImporter)
class LessonOverviewsImporter(BaseSectionImporter):

    __LESSONS__ = 'Lessons'

    @Lazy
    def current_principal(self):
        remoteUser = IPrincipal(get_remote_user(), None)
        if remoteUser is None:
            remoteUser = current_principal(True)
        return remoteUser

    def _post_process_asset(self, asset, source_filer, target_filer):
        # save asset resources
        # make sure we transfer from concrete
        concrete = IConcreteAsset(asset, asset)
        transfer_resources_from_filer(interface_of_asset(concrete),
                                      concrete,
                                      source_filer,
                                      target_filer)
        # set creator
        concrete.creator = asset.creator = self.current_principal.id
        # mark as created
        interface.alsoProvides(asset, IUserCreatedAsset)
        if not IContentBackedPresentationAsset.providedBy(concrete):
            interface.alsoProvides(concrete, IUserCreatedAsset)
        # check 'children'
        if IItemAssetContainer.providedBy(asset):
            asset_items = asset.Items if asset.Items is not None else ()
            for item in asset_items:
                self._post_process_asset(item, source_filer, target_filer)
        # set proper target
        check_docket_targets(concrete)

    def _get_course_site(self, course):
        return IHostPolicyFolder(course)

    def _sync_lessons(self, course, bucket):
        return synchronize_course_lesson_overview(course, buckets=(bucket,))

    def _do_import(self, context, source_filer, save_sources=True):
        course = ICourseInstance(context)
        entry = ICourseCatalogEntry(course)
        site = self._get_course_site(course)
        target_filer = get_course_filer(course)
        # check there is a 'Lessons' folder
        if source_filer.is_bucket(self.__LESSONS__):
            bucket = source_filer.get(self.__LESSONS__)
            with current_site(site):
                named_sites = (site.__name__,)
                registry = site.getSiteManager()
                # clear assets - not merging
                clear_course_assets(course)
                clear_namespace_last_modified(course)
                remove_and_unindex_course_assets(namespace=entry.ntiid,
                                                 registry=registry,
                                                 course=course,
                                                 sites=named_sites,
                                                 force=True)  # not merging
                # load assets
                lessons = self._sync_lessons(course, bucket)
                for lesson in lessons or ():
                    self._post_process_asset(lesson,
                                             source_filer,
                                             target_filer)
            # save sources in main course Lessos folder
            root = get_parent_course(course).root
            if save_sources and IFilesystemBucket.providedBy(root):
                out_path = os.path.join(root.absolute_path, self.__LESSONS__)
                self.makedirs(out_path)  # create
                for path in source_filer.list(self.__LESSONS__):
                    if not source_filer.is_bucket(path):
                        source = source_filer.get(path)
                        name = source_filer.key_name(path)
                        new_path = os.path.join(out_path, name)
                        transfer_to_native_file(source, new_path)
            return lessons
        return ()

    def process(self, context, filer, writeout=True):
        result = []
        course = ICourseInstance(context)
        result.extend(self._do_import(context, filer, writeout))
        for sub_instance in get_course_subinstances(course):
            if sub_instance.Outline is not course.Outline:
                result.extend(self._do_import(sub_instance, filer, writeout))
        return tuple(result)
