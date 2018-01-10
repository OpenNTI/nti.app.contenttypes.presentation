#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os

from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import site as current_site

from zope.security.interfaces import IPrincipal

from nti.app.authentication import get_remote_user

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.synchronizer import clear_course_assets
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import remove_and_unindex_course_assets
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.contenttypes.presentation.utils.asset import intid_register
from nti.app.contenttypes.presentation.utils.asset import check_docket_targets

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.utils import transfer_resources_from_filer

from nti.cabinet.filer import transfer_to_native_file

from nti.contentlibrary.indexed_data import get_library_catalog

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

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from nti.site.interfaces import IHostPolicyFolder

from nti.site.utils import registerUtility

__LESSONS__ = 'Lessons'

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseSectionImporter)
class AssetCleanerImporter(BaseSectionImporter):
    """
    An importer that remove all course assets
    """

    def _clear_assets(self, course, site):
        registry = site.getSiteManager()
        clear_course_assets(course)
        clear_namespace_last_modified(course)
        named_sites = (site.__name__,)
        entry_ntiid = ICourseCatalogEntry(course).ntiid
        remove_and_unindex_course_assets(namespace=entry_ntiid,
                                         registry=registry,
                                         course=course,
                                         sites=named_sites,
                                         force=True)

    def _do_clean(self, course, unused_filer, unused_writeout):
        result = []
        site = IHostPolicyFolder(course)
        with current_site(site):
            self._clear_assets(course, site)
        return result

    def process(self, context, filer, writeout=True):
        result = []
        course = ICourseInstance(context)
        bucket = self.course_bucket_path(course)
        bucket = os.path.join(bucket, __LESSONS__)
        # check there is a 'Lessons' folder
        if filer.is_bucket(bucket):
            self._do_clean(context, filer, writeout)
        for sub_instance in get_course_subinstances(course):
            if sub_instance.Outline is not course.Outline:
                self.process(sub_instance, filer, writeout)
        return result


@interface.implementer(ICourseSectionImporter)
class LessonOverviewsImporter(BaseSectionImporter):

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
            for item in asset.Items or ():
                self._post_process_asset(item, source_filer, target_filer)
        # set proper target
        check_docket_targets(concrete)

    def _sync_lessons(self, course, bucket):
        return synchronize_course_lesson_overview(course,
                                                  buckets=(bucket,),
                                                  auto_roll_coalesce=False,
                                                  default_publish=False)

    def _do_import(self, context, source_filer, save_sources=True):
        course = ICourseInstance(context)
        site = IHostPolicyFolder(course)
        target_filer = get_course_filer(course)
        bucket = self.course_bucket_path(course)
        bucket = os.path.join(bucket, __LESSONS__)
        # check there is a 'Lessons' folder
        if source_filer.is_bucket(bucket):
            bucket = source_filer.get(bucket)
            with current_site(site):
                # load assets
                lessons = self._sync_lessons(course, bucket)
                for lesson in lessons or ():
                    self._post_process_asset(lesson,
                                             source_filer,
                                             target_filer)
            # save sources in main course Lessos folder
            root = get_parent_course(course).root
            if save_sources and IFilesystemBucket.providedBy(root):
                out_path = os.path.join(root.absolute_path, __LESSONS__)
                self.makedirs(out_path)  # create
                for path in source_filer.list(__LESSONS__):
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
        return result


@interface.implementer(ICourseSectionImporter)
class UserAssetsImporter(BaseSectionImporter):
    """
    An importer that creates and stores user created assets within our course.
    """

    __USER_ASSETS__ = 'user_assets.json'

    def _save_source(self, course, source_file, bucket):
        """
        Save our source file to our course bucket.
        """
        root = course.root
        if IFilesystemBucket.providedBy(root):
            out_path = os.path.join(root.absolute_path, bucket)
            self.makedirs(out_path)
            out_path = os.path.join(out_path, self.__USER_ASSETS__)
            transfer_to_native_file(source_file, out_path)

    def _create_asset(self, source, course, site):
        """
        Create the asset; put in container, set creator, intid, index.
        """
        registry = site.getSiteManager()
        factory = find_factory_for(source)
        asset = factory()  # create object
        update_from_external_object(asset, source, notify=False)
        interface.alsoProvides(asset, IUserCreatedAsset)
        # This puts in course container and sets creator.
        processor = IPresentationAssetProcessor(asset)
        processor.handle(asset, course)
        intid_register(asset, registry)
        # Index and register
        provided = interface_of_asset(asset)
        entry_ntiid = ICourseCatalogEntry(course).ntiid
        logger.info("[%s] Registering imported asset (%s)",
                    site.__name__, asset.ntiid)
        registerUtility(registry,
                        component=asset,
                        provided=provided,
                        name=asset.ntiid)
        container_ntiids = (entry_ntiid,)
        catalog = get_library_catalog()
        catalog.index(asset,
                      container_ntiids=container_ntiids,
                      namespace=entry_ntiid,
                      sites=site.__name__)
        return asset

    def _do_import(self, course, filer, writeout=True):
        result = []
        site = IHostPolicyFolder(course)
        entry = ICourseCatalogEntry(course)
        with current_site(site):
            # check for user asset source
            bucket = self.course_bucket_path(course)
            source_file = filer.get(self.__USER_ASSETS__, bucket)
            if source_file is not None:
                source = self.load(source_file)
                if writeout:
                    self._save_source(course, source_file, bucket)
                for asset_source in source:
                    asset = self._create_asset(asset_source, course, site)
                    result.append(asset)
        logger.info('Imported %s user created assets in %s',
                    len(result), entry.ntiid)
        return result

    def process(self, context, filer, writeout=True):
        result = []
        course = ICourseInstance(context)
        result.extend(self._do_import(context, filer, writeout))
        for sub_instance in get_course_subinstances(course):
            if sub_instance.Outline is not course.Outline:
                result.extend(self._do_import(sub_instance, filer, writeout))
        return result
