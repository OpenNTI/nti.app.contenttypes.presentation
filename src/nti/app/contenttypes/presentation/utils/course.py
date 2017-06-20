# #!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.component.hooks import getSite

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses.interfaces import NTIID_ENTRY_TYPE

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPersistentCourseCatalog

from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES

from nti.ntiids.ntiids import is_ntiid_of_type
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names


def get_courses_for_pacakge(ntiid, sites=None):
    result = get_courses_for_packages(sites, ntiid)
    return result


def get_containers(ntiids=()):
    result = []
    for ntiid in ntiids or ():
        context = find_object_with_ntiid(ntiid)
        if ICourseCatalogEntry.providedBy(context):
            context = ICourseInstance(context, None)
        if context is not None:
            result.append(context)
    return result


def get_courses(ntiids=()):
    result = set()
    content_ntiids = set()
    for ntiid in ntiids or ():
        # As shortcut, we only want our entry types. This
        # prevents expensive lookups of content units.
        if not is_ntiid_of_type(ntiid, NTIID_ENTRY_TYPE):
            content_ntiids.add(ntiid)
            continue
        course = None
        context = find_object_with_ntiid(ntiid)
        if     ICourseInstance.providedBy(context) \
            or ICourseCatalogEntry.providedBy(context):
            course = ICourseInstance(context, None)
        if course is not None:
            result.add(course)
    if not result:
        # If not courses, see if we can resolve via content.
        for content_ntiid in content_ntiids:
            context = find_object_with_ntiid(content_ntiid)
            if IContentPackage.providedBy(context):
                course = ICourseInstance(context, None)
                if course is not None:
                    result.add(course)
    return result


def get_presentation_asset_courses(item):
    catalog = get_library_catalog()
    entries = catalog.get_containers(item)
    return get_courses(entries) if entries else ()


def get_presentation_asset_containers(item):
    catalog = get_library_catalog()
    entries = catalog.get_containers(item)
    return get_containers(entries) if entries else ()


def find_course_by_parts(catalog, parts=()):
    result = None
    context = catalog
    parts = list(parts)
    while parts:
        # check context
        if not context:
            break
        try:
            name = parts.pop(0)
            # Underscore parts are given, so we'll want to replace with
            # the possible space-inclusive keys we have in our folder
            # structure.
            transformed = name.replace('_', ' ')
            # find in context
            if name in context:
                context = context[name]
            elif transformed in context:
                context = context[transformed]
            else:
                break  # nothing found
            # check for course
            if ICourseInstance.providedBy(context):
                if not parts:  # nothing more
                    result = context
                    break
                context = context.SubInstances
        except (TypeError, IndexError):
            logger.exception("Invalid context or parts", context)
            break
        except KeyError:
            logger.error("Invalid key %s in context %s", name, context)
            break
    return result


def get_course_by_relative_path_parts(parts=()):
    context = component.queryUtility(IPersistentCourseCatalog)
    while context is not None:
        result = find_course_by_parts(context, parts)
        if result is not None:
            return result
        context = component.queryNextUtility(context, IPersistentCourseCatalog)
    logger.debug("Could not find a course for paths '%s' under site '%s'",
                 parts, getSite().__name__)
    return None


def get_entry_by_relative_path_parts(parts=()):
    course = get_course_by_relative_path_parts(parts)
    result = ICourseCatalogEntry(course, None)
    return result


def remove_package_assets_from_course_container(package_ntiid, course):
    """
    Remove all assets from the given package ntiid from having
    the given course as a container.
    """
    package_ntiids = (package_ntiid,)
    entry = ICourseCatalogEntry(course)
    logger.info("Removing referenced assets to course (course=%s) (packages=%s)",
                entry.ntiid, package_ntiids)
    catalog = get_library_catalog()
    sites = get_component_hierarchy_names()
    # We are assuming no assets can exist in multiple packages.
    removed_doc_ids = catalog.get_references(provided=PACKAGE_CONTAINER_INTERFACES,
                                             container_ntiids=package_ntiids,
                                             container_all_of=False,
                                             sites=sites)
    for doc_id in removed_doc_ids or ():
        catalog.remove_containers(doc_id, (entry.ntiid,))
    return len(removed_doc_ids)
