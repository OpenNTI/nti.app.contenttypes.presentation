#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.component.hooks import getSite

from zope.event import notify as event_notify

from nti.app.base.abstract_views import get_safe_source_filename

from nti.app.contenttypes.presentation.utils import add_2_connection
from nti.app.contenttypes.presentation.utils import make_asset_ntiid

from nti.app.products.courseware.resources.utils import get_course_filer
from nti.app.products.courseware.resources.utils import is_internal_file_link

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.interfaces import PresentationAssetCreatedEvent

from nti.coremetadata.utils import current_principal

from nti.publishing.interfaces import IPublishable

from nti.site.utils import registerUtility


def principalId():
    current_principal(True).id


def notify_created(item, principal=None, externalValue=None):
    add_2_connection(item)  # required
    principal = principal or principalId()  # always get a principal
    event_notify(PresentationAssetCreatedEvent(item, principal, externalValue))
    if IPublishable.providedBy(item) and item.is_published():
        item.unpublish(event=False)


def add_to_course(context, item):
    course = ICourseInstance(context, None)
    if course is not None:
        container = IPresentationAssetContainer(course, None)
        container[item.ntiid] = item


def add_to_courses(context, item):
    add_to_course(context, item)
    for subinstance in get_course_subinstances(context):
        add_to_course(subinstance, item)


def add_to_container(context, item):
    result = []
    add_to_courses(context, item)
    entry = ICourseCatalogEntry(context, None)
    if entry is not None:
        result.append(entry.ntiid)
    return result


def register_utility(registry, item, provided, name=None):
    name = name or item.ntiid
    registerUtility(registry, item, provided, name=name)


def get_site_registry(registry=None):
    if registry is None:
        site = getSite()
        if site is None:
            registry = component.getGlobalSiteManager()
        else:
            registry = component.getSiteManager()
    return registry


def canonicalize(items, creator, base=None, registry=None):
    result = []
    registry = get_site_registry(registry)
    for idx, item in enumerate(items or ()):
        created = True
        provided = iface_of_asset(item)
        if not item.ntiid:
            item.ntiid = make_asset_ntiid(provided, base=base, extra=idx)
        else:
            stored = registry.queryUtility(provided, name=item.ntiid)
            if stored is not None:
                created = False
                items[idx] = stored
        if created:
            result.append(item)
            item.creator = creator
            register_utility(registry, item, provided, name=item.ntiid)
    return result


def handle_multipart(context, user, contentObject, sources, provided=None):
    filer = get_course_filer(context, user)
    provided = iface_of_asset(contentObject) if provided is None else provided
    for name, source in sources.items():
        if name in provided:
            # remove existing
            location = getattr(contentObject, name, None)
            if location and is_internal_file_link(location):
                filer.remove(location)
            # save a in a new file
            key = get_safe_source_filename(source, name)
            location = filer.save(key, source,
                                  overwrite=False,
                                  structure=True,
                                  context=contentObject)
            setattr(contentObject, name, location)
