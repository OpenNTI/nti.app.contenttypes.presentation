# #!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.container.contained import Contained

from zope.security.interfaces import IPrincipal

from nti.appserver.pyramid_authorization import has_permission

from nti.base.mixins import CreatedAndModifiedTimeMixin

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import NTIID_ENTRY_TYPE

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPersistentCourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import get_any_enrollment
from nti.contenttypes.courses.utils import get_course_hierarchy
from nti.contenttypes.courses.utils import get_courses_for_packages
from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.ntiids.ntiids import is_ntiid_of_type
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import get_host_site

from nti.site.site import get_component_hierarchy_names


@interface.implementer(ICourseInstanceEnrollmentRecord)
class ProxyEnrollmentRecord(CreatedAndModifiedTimeMixin, Contained):

    Scope = None
    Principal = None
    CourseInstance = None

    def __init__(self, course=None, principal=None, scope=None):
        self.Scope = scope
        self.Principal = principal
        self.CourseInstance = course


def get_enrollment_record(context, user):
    course = ICourseInstance(context, None)  # e.g. course in lineage
    if course is None:
        return None
    else:
        is_editor = has_permission(ACT_CONTENT_EDIT, course)
        # give priority to course in lineage before checking the rest
        for instance in get_course_hierarchy(course):
            if is_course_instructor_or_editor(instance, user) or is_editor:
                # create a fake enrollment record w/ all scopes to signal an
                # instructor
                return ProxyEnrollmentRecord(course, IPrincipal(user), ES_ALL)
        # find any enrollment
        result = get_any_enrollment(course, user)
        return result


def get_courses_for_pacakge(ntiid):
    sites = get_component_hierarchy_names()
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
    for ntiid in ntiids or ():
        # As shortcut, we only want our entry types.This
        # prevents expensive lookups of content units.
        if not is_ntiid_of_type(ntiid, NTIID_ENTRY_TYPE):
            continue
        course = None
        context = find_object_with_ntiid(ntiid)
        if 		ICourseInstance.providedBy(context) \
                or ICourseCatalogEntry.providedBy(context):
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
    for site in get_component_hierarchy_names():
        with current_site(get_host_site(site)):
            context = component.queryUtility(IPersistentCourseCatalog)
            if not context:
                continue
            result = find_course_by_parts(context, parts)
            if result is not None:
                return result

    logger.debug("Could not find a course for paths '%s' under site '%s'",
                 parts, getSite().__name__)
    return None


def get_entry_by_relative_path_parts(parts=()):
    course = get_course_by_relative_path_parts(parts)
    result = ICourseCatalogEntry(course, None)
    return result
