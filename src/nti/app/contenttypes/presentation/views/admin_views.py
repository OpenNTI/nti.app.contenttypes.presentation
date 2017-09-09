#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from requests.structures import CaseInsensitiveDict

from zope import component

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.utils import transfer_resources_from_filer

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.utils.common import course_assets

from nti.app.contenttypes.presentation.utils.course import remove_package_assets_from_course_container

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.cabinet.filer import DirectoryFiler

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_packages

from nti.contenttypes.presentation import interface_of_asset

from nti.contenttypes.presentation.index import get_assets_catalog

from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IDataserverFolder

from nti.dataserver.metadata.index import get_metadata_catalog

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import get_all_host_sites

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             permission=nauth.ACT_NTI_ADMIN,
             context=IDataserverFolder,
             name='RebuildPresentationAssetCatalog')
class RebuildPresentationAssetCatalogView(AbstractAuthenticatedView):

    def __call__(self):
        intids = component.getUtility(IIntIds)
        # clear indexes
        catalog = get_assets_catalog()
        for index in catalog.values():
            index.clear()
        metadata = get_metadata_catalog()
        # reindex
        seen = set()
        items = dict()
        for host_site in get_all_host_sites():  # check all sites
            with current_site(host_site):
                count = 0
                for unused, asset in component.getUtilitiesFor(IPresentationAsset):
                    doc_id = intids.queryId(asset)
                    if doc_id is None or doc_id in seen:
                        continue
                    count += 1
                    seen.add(doc_id)
                    catalog.index_doc(doc_id, asset)
                    metadata.index_doc(doc_id, asset)
                items[host_site.__name__] = count
                logger.info("%s asset(s) indexed in site %s",
                            count, host_site.__name__)
        result = LocatedExternalDict()
        result[ITEMS] = items
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
        for unused_key, item, unused_container in course_assets(course):
            asset = IConcreteAsset(item, item)
            transfer_result = transfer_resources_from_filer(interface_of_asset(asset),
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


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_NTI_ADMIN,
               name='FixCourseAssetContainers')
class FixCourseAssetContainersView(AbstractAuthenticatedView,
                                   ModeledContentUploadRequestUtilsMixin):
    """
    Update the containers for course assts by removing all
    assets given by `package` from the course containers.

    The package cannot currently be a course package.
    """

    def readInput(self, value=None):
        if self.request.body:
            values = super(FixCourseAssetContainersView, self).readInput(value)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def _get_package_ntiid(self, course):
        params = self.readInput()
        result = params.get('ntiid') \
              or params.get('package') \
              or params.get('package_ntiid')
        if result is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Must provide package ntiid.'),
                                 'field': 'ntiid'
                             },
                             None)
        package = find_object_with_ntiid(result)
        packages = get_course_packages(course)
        if package is not None and package in packages or ():
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Cannot remove package reference.'),
                                 'code': 'CannotRemovePackageReferenceError'
                             },
                             None)
        return result

    def __call__(self):
        result = LocatedExternalDict()
        course = ICourseInstance(self.context)
        package_ntiid = self._get_package_ntiid(course)
        count = remove_package_assets_from_course_container(package_ntiid, 
                                                            course)
        entry_ntiid = ICourseCatalogEntry(course).ntiid
        logger.info('Removed %s package assets from course containers (%s) (%s)',
                    count, package_ntiid, entry_ntiid)
        result["RemovedCount"] = count
        return result
