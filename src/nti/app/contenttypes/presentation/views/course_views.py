#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.view import view_config
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

from zope import component

from zope.intid.interfaces import IIntIds

from zope.mimetype.interfaces import IContentTypeAware

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.presentation.views import VIEW_ASSETS
from nti.app.contenttypes.presentation.views import VIEW_COURSE_CONTENT_LIBRARY_SUMMARY

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseContentLibraryProvider

from nti.contenttypes.courses.utils import get_parent_course

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES
from nti.contenttypes.presentation import asset_iface_with_mimetype

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.site.site import get_component_hierarchy_names

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

logger = __import__('logging').getLogger(__name__)


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_ASSETS,
               request_method='GET',
               permission=nauth.ACT_CONTENT_EDIT)
class CoursePresentationAssetsView(AbstractAuthenticatedView,
                                   BatchingUtilsMixin):

    def get_mimeTypes(self):
        params = CaseInsensitiveDict(self.request.params)
        accept = params.get('accept') or params.get('mimeTypes') or ''
        accept = accept.split(',') if accept else ()
        if accept and '*/*' not in accept:
            accept = {e.strip().lower() for e in accept if e}
            accept.discard('')
        else:
            accept = ()
        return accept

    def pkg_containers(self, pacakge):
        result = []
        def recur(unit):
            for child in unit.children or ():
                recur(child)
            result.append(unit.ntiid)
        recur(pacakge)
        return result

    def course_containers(self, course):
        result = set()
        courses = {course, get_parent_course(course)}
        courses.discard(None)
        for _course in courses:
            entry = ICourseCatalogEntry(_course)
            for package in get_course_packages(_course):
                result.update(self.pkg_containers(package))
            result.add(entry.ntiid)
        return result

    def isBatching(self):
        size, start = self._get_batch_size_start()
        return bool(size is not None and start is not None)

    def _provided(self, mimeTypes):
        if not mimeTypes:
            return ALL_PRESENTATION_ASSETS_INTERFACES

        ifaces = set()
        for mimeType in mimeTypes:
            _iface = asset_iface_with_mimetype(mimeType)
            if _iface:
                ifaces.add(_iface)
        return tuple(ifaces)

    def yield_course_items(self, course, mimeTypes=()):
        catalog = get_library_catalog()
        intids = component.getUtility(IIntIds)
        container_ntiids = self.course_containers(course)
        ifaces = self._provided(mimeTypes)
        if not ifaces:
            return

        for item in catalog.search_objects(intids=intids,
                                           container_all_of=False,
                                           container_ntiids=container_ntiids,
                                           sites=get_component_hierarchy_names(),
                                           provided=ifaces):
            yield item

    def _do_call(self):
        batching = self.isBatching()
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        self.request.acl_decoration = not batching  # decoration

        mimeTypes = self.get_mimeTypes()
        course = ICourseInstance(self.context)

        result[ITEMS] = items = []
        items.extend(x for x in self.yield_course_items(course, mimeTypes))
        items.sort()  # natural order
        lastModified = reduce(
            lambda x, y: max(x, getattr(y, 'lastModified', 0)), items, 0
        )

        if batching:
            self._batch_items_iterable(result, items)
        else:
            result[ITEM_COUNT] = len(items)

        result[TOTAL] = len(items)
        result[LAST_MODIFIED] = result.lastModified = lastModified
        return result

    def __call__(self):
        return self._do_call()


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_COURSE_CONTENT_LIBRARY_SUMMARY,
               request_method='GET',
               permission=nauth.ACT_CONTENT_EDIT)
class CourseContentLibraryView(AbstractAuthenticatedView):
    """
    A view that exposes course content information, defined as those mimetypes
    that either exist in a course or could be added to a course. Useful when
    determining which presentation assets can be added to course lessons.
    """

    def __call__(self):
        course = ICourseInstance(self.context)
        providers = component.subscribers((self.remoteUser, course),
                                          ICourseContentLibraryProvider)
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        result[ITEMS] = items = []

        for provider in providers or ():
            mime_types = provider.get_item_mime_types()
            if mime_types:
                items.extend(mime_types)
        result[ITEM_COUNT] = len(items)

        result[TOTAL] = len(items)
        return result
