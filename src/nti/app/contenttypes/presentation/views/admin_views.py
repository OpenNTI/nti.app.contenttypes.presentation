#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

import transaction

from zope import component, lifecycleevent

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from ZODB.POSException import POSError

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

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.presentation import interface_of_asset

from nti.contenttypes.presentation.index import get_assets_catalog

from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraint

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IDataserverFolder

from nti.dataserver.metadata.index import IX_MIMETYPE
from nti.dataserver.metadata.index import get_metadata_catalog

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.intid.common import removeIntId

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import get_all_host_sites

from nti.zodb import isBroken

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             permission=nauth.ACT_NTI_ADMIN,
             context=IDataserverFolder,
             name='RebuildPresentationAssetCatalog')
class RebuildPresentationAssetCatalogView(AbstractAuthenticatedView):

    @Lazy
    def assets(self):
        return get_assets_catalog()

    @Lazy
    def metadata(self):
        return get_metadata_catalog()

    def index_doc(self, doc_id, asset):
        # pylint: disable=no-member
        try:
            self.assets.index_doc(doc_id, asset)
            self.metadata.index_doc(doc_id, asset)
        except POSError:
            logger.error("Error while indexing asset %s/%s",
                         doc_id, type(asset))
            return False
        return True

    def __call__(self):
        intids = component.getUtility(IIntIds)
        # clear indexes
        # pylint: disable=no-member
        for index in self.assets.values():
            index.clear()
        # reindex
        seen = set()
        items = dict()
        for host_site in get_all_host_sites():  # check all sites
            with current_site(host_site):
                count = 0
                expensive = {}
                # process assets
                for unused_name, asset in list(component.getUtilitiesFor(IPresentationAsset)):
                    doc_id = intids.queryId(asset)
                    if doc_id is None or doc_id in seen:
                        continue
                    seen.add(doc_id)
                    if INTISlide.providedBy(asset) or INTISlideVideo.providedBy(asset):
                        expensive[doc_id] = asset
                    elif self.index_doc(doc_id, asset):
                        count += 1
                        if count % 1000 == 0:
                            logger.info('Processed %s objects...', count)
                            transaction.savepoint(optimistic=True)
                # process expensive items
                for doc_id, asset in expensive.items():
                    if self.index_doc(doc_id, asset):
                        count += 1
                        if count % 1000 == 0:
                            logger.info('Processed %s objects...', count)
                            transaction.savepoint(optimistic=True)
                items[host_site.__name__] = count
                logger.info("%s asset(s) indexed in site %s",
                            count, host_site.__name__)
        result = LocatedExternalDict()
        result[ITEMS] = items
        result[ITEM_COUNT] = result[TOTAL] = len(seen)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             permission=nauth.ACT_NTI_ADMIN,
             context=IDataserverFolder,
             name='RemoveInvalidLessonConstraints')
class RemoveInvalidLessonConstraintsView(AbstractAuthenticatedView):

    @property
    def mimeTypes(self):
        return ("application/vnd.nextthought.lesson.assignmentcompletionconstraint",
                "application/vnd.nextthought.lesson.surveycompletionconstraint")

    def __call__(self):
        catalog = get_metadata_catalog()
        query = {
            IX_MIMETYPE: {'any_of': self.mimeTypes},
        }
        count = 0
        containers = set()
        result = LocatedExternalDict()
        intids = component.getUtility(IIntIds)
        for doc_id in catalog.apply(query) or ():
            constraint = intids.queryObject(doc_id)
            if not ILessonPublicationConstraint.providedBy(constraint):
                continue
            lesson = INTILessonOverview(constraint, None)
            if intids.queryId(lesson) is None:
                count += 1
                removeIntId(constraint)
                # pylint: disable=protected-access
                if not isBroken(constraint.__parent__):
                    # add container
                    containers.add(constraint.__parent__)

        # clear containers:
        containers.discard(None)
        for container in containers:
            try:
                container.clear()
            except Exception:  # pylint: broad-except
                pass
            lifecycleevent.removed(container)
            container.__parent__ = None

        result["RemovedCount"] = count
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
            # pylint: disable=too-many-function-args
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
        count = remove_package_assets_from_course_container(
            package_ntiid, course
        )
        entry_ntiid = ICourseCatalogEntry(course).ntiid
        logger.info('Removed %s package assets from course containers (%s) (%s)',
                    count, package_ntiid, entry_ntiid)
        result["RemovedCount"] = count
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IDataserverFolder,
             request_method='GET',
             name="AssetContainerAudit",
             permission=nauth.ACT_NTI_ADMIN)
class AssetContainerAuditView(AbstractAuthenticatedView):
    """
    A view to find assets that are present in more than one
    IPresentationAssetContainer. This should only occur in top level
    containers due to a bug in early 2017. Thus, we dont have to traverse
    through children.
    """

    @Lazy
    def _params(self):
        values = self.request.params
        return CaseInsensitiveDict(values)

    def perform_audit(self, seen):
        """
        Return a dict of asset_ntiid -> list of multiple packages containing
        that asset.
        """
        result = dict()
        asset_packages = dict()
        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            for package in library.contentPackages:
                if package.ntiid not in seen:
                    seen.add(package.ntiid)
                    asset_ntiids = tuple(IPresentationAssetContainer(package))
                    for asset_ntiid in asset_ntiids or ():
                        asset_packages.setdefault(asset_ntiid, [])
                        asset_packages[asset_ntiid].append(package.ntiid)
        for asset_ntiid, package_ntiids in asset_packages.items():
            if len(package_ntiids) > 1:
                result[asset_ntiid] = package_ntiids
        return result

    def __call__(self):
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        seen = set()
        result[ITEMS] = items = dict()
        if 'all_sites' in self._params:
            for host_site in get_all_host_sites():
                with current_site(host_site):
                    site_result = self.perform_audit(seen)
                    if site_result:
                        items[host_site.__name__] = site_result
        else:
            site_result = self.perform_audit(seen)
            items[getSite().__name__] = site_result
        result['SiteCount'] = len(items)
        result['PackageCount'] = sum(len(x) for x in items.values())
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             permission=nauth.ACT_NTI_ADMIN,
             context=IDataserverFolder,
             name='FixRelatedWorkRefHrefs')
class FixRelatedWorkRefHrefsView(AbstractAuthenticatedView):
    """
    Some related work refs had their `href` attribute updated (usually during
    icon updates). This caused the icon to have an absolute path via a content
    package, which would break if the content package was ever updated to a
    new location (via ImportRenderedContent). This view will simply revert the
    ref href to a `resources` relative path.
    """

    def __call__(self):
        catalog = get_library_catalog()
        intids = component.getUtility(IIntIds)
        provided = (INTIRelatedWorkRef,)
        rs = catalog.search_objects(intids=intids,
                                    provided=provided)
        related_work_refs = tuple(rs)
        result = LocatedExternalDict()
        result[ITEMS] = items = dict()
        count = 0
        for ref in related_work_refs or ():
            if ref.href and ref.href.startswith('/content/'):
                old_href = ref.href
                new_href = 'resources%s' % (old_href.split('resources')[-1])
                ref.href = new_href
                items[ref.ntiid] = (old_href, new_href)
                count += 1
        result["UpdatedCount"] = count
        return result
