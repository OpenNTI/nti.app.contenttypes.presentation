#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from pyramid.location import lineage

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.index import get_assets_catalog

from nti.contenttypes.presentation.interfaces import IPointer
from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import ISiteAdapter
from nti.contenttypes.presentation.interfaces import INTIIDAdapter
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import ITargetAdapter
from nti.contenttypes.presentation.interfaces import INamespaceAdapter
from nti.contenttypes.presentation.interfaces import ISlideDeckAdapter
from nti.contenttypes.presentation.interfaces import IContainersAdapter
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IContainedTypeAdapter

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface


# Site


class _Site(object):

    __slots__ = ('site',)

    def __init__(self, site):
        self.site = site


@interface.implementer(ISiteAdapter)
@component.adapter(IPresentationAsset)
def _asset_to_site(context):
    folder = find_interface(context, IHostPolicyFolder, strict=False)
    if folder is not None:
        return _Site(folder.__name__)


# Type


class _Type(object):

    __slots__ = ('type',)

    def __init__(self, type_):
        self.type = type_


@component.adapter(IPresentationAsset)
@interface.implementer(IContainedTypeAdapter)
def _asset_to_contained_type(context):
    provided = iface_of_asset(context)
    return _Type(provided.__name__)


# Namespace


class _Namespace(object):

    __slots__ = ('namespace',)

    def __init__(self, namespace):
        self.namespace = namespace


def _course_outline_namespace(context):
    node = find_interface(context, ICourseOutlineNode, strict=False)
    if node is not None:
        return getattr(node, 'src', None)
    return None


@component.adapter(IPresentationAsset)
@interface.implementer(INamespaceAdapter)
def _asset_to_namespace(context):
    source = _course_outline_namespace(context)
    if source:
        result = _Namespace(source)
    else:
        package = find_interface(context, IContentPackage, strict=False)
        result = _Namespace(package.ntiid) if package is not None else None
    return result


# NTIID


class _NTIID(object):

    __slots__ = ('ntiid',)

    def __init__(self, ntiid):
        self.ntiid = ntiid


@interface.implementer(INTIIDAdapter)
@component.adapter(IPresentationAsset)
def _asset_to_ntiid(context):
    return _NTIID(context.ntiid)


# Target


class _Target(object):

    __slots__ = ('target',)

    def __init__(self, target):
        self.target = target


@component.adapter(IPresentationAsset)
@interface.implementer(ITargetAdapter)
def _asset_to_target(context):
    if IPointer.providedBy(context) or IAssetRef.providedBy(context):
        return _Target(context.target)
    return None


# Containers


class _Containers(object):

    __slots__ = ('containers',)

    def __init__(self, containers):
        self.containers = containers


def _package_lineage_to_containers(context):
    result = set()
    for location in lineage(context):
        if IContentUnit.providedBy(location):
            result.add(location.ntiid)
        if IContentPackage.providedBy(location):
            break
    result.discard(None)
    return result


def _entry_ntiid(context):
    entry = ICourseCatalogEntry(context, None)
    return getattr(entry, 'ntiid', None)


def _course_lineage_to_containers(context):
    course = None
    result = set()
    for location in lineage(context):
        if context is location:
            continue
        if IPresentationAsset.providedBy(location):
            result.add(location.ntiid)
        if ICourseInstance.providedBy(location):
            course = location
            result.add(_entry_ntiid(course))
            break
    # include subinstances
    for instance in get_course_subinstances(course):
        if instance.Outline is course.Outline:
            result.add(_entry_ntiid(course))
    result.discard(None)
    return result


@component.adapter(IPresentationAsset)
@interface.implementer(IContainersAdapter)
def _asset_to_containers(context):
    containers = set()
    package = find_interface(context, IContentPackage, strict=False)
    if package is not None:  # package asset
        containers.update(_package_lineage_to_containers(context))
    else:  # course asset
        containers.update(_course_lineage_to_containers(context))
    containers.discard(None)
    containers.discard(context.ntiid)
    return _Containers(tuple(containers))


@component.adapter(INTISlideVideo)
@interface.implementer(IContainersAdapter)
def _slide_video_to_containers(context):
    containers = _asset_to_containers(context)
    containers = set(containers.containers or ())
    package = find_interface(context, IContentPackage, strict=False)
    if package is not None:
        catalog = get_assets_catalog()
        courses = get_courses_for_packages(packages=package.ntiid)
        for course in courses or ():
            entry = ICourseCatalogEntry(course, None)
            if entry is None:
                continue
            # query all video and video refs in the course
            site = IHostPolicyFolder(course)
            refs = catalog.get_references(provided=INTIVideoRef,
                                          target=context.video_ntiid,
                                          container_ntiids=entry.ntiid,
                                          container_all_of=False,
                                          sites=site.__name__)
            if refs:
                containers.add(entry.ntiid)
            else:
                videos = catalog.get_references(provided=INTIVideo,
                                                ntiid=context.video_ntiid,
                                                container_ntiids=entry.ntiid,
                                                container_all_of=False,
                                                sites=site.__name__)
                if videos:
                    containers.add(entry.ntiid)

    # include the parent slide deck
    if      context.__parent__ is not None \
        and context.__parent__.ntiid:
        containers.add(context.__parent__.ntiid)
    return _Containers(tuple(containers))


@component.adapter(INTISlide)
@interface.implementer(IContainersAdapter)
def _slide_to_containers(context):
    containers = _asset_to_containers(context)
    containers = set(containers.containers or ())
    if      context.__parent__ is not None \
        and context.__parent__.ntiid:
        containers.add(context.__parent__.ntiid)
    return _Containers(tuple(containers))


# Slide deck


class _SlideDeck(object):

    __slots__ = ('videos',)

    def __init__(self, videos):
        self.videos = videos


@component.adapter(INTISlideDeck)
@interface.implementer(ISlideDeckAdapter)
def _slideck_data(context):
    videos = {v.video_ntiid for v in context.Videos or ()}
    return _SlideDeck(videos)
