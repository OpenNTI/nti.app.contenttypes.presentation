#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from itertools import chain

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.interface.interfaces import IUnregistered

from zope.intid.interfaces import IIntIdAddedEvent

from zope.event import notify

from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from zope.security.management import queryInteraction

from zc.intid.interfaces import IAfterIdAddedEvent
from zc.intid.interfaces import IBeforeIdRemovedEvent

from nti.app.assessment.common import get_evaluation_courses

from nti.app.contenttypes.presentation.synchronizer import clear_course_assets
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import remove_and_unindex_course_assets
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_containers
from nti.app.contenttypes.presentation.utils.course import remove_package_assets_from_course_container

from nti.app.products.courseware.resources.utils import is_internal_file_link
from nti.app.products.courseware.resources.utils import to_external_file_link
from nti.app.products.courseware.resources.utils import get_file_from_external_link

from nti.app.products.courseware.utils import get_content_related_work_refs

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQEvaluation
from nti.assessment.interfaces import IQuestionSet
from nti.assessment.interfaces import IQEditableEvaluation

from nti.contentfile.interfaces import IContentBaseFile

from nti.contentlibrary.indexed_data import get_site_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentUnitRemovedEvent
from nti.contentlibrary.interfaces import IContentUnitAssociations
from nti.contentlibrary.interfaces import IContentPackageRemovedEvent

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseBundleUpdatedEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceAvailableEvent

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.presentation.interfaces import TRX_ASSET_MOVE_TYPE
from nti.contenttypes.presentation.interfaces import TRX_OVERVIEW_GROUP_MOVE_TYPE
from nti.contenttypes.presentation.interfaces import TRX_ASSET_REMOVED_FROM_ITEM_ASSET_CONTAINER

from nti.contenttypes.presentation.interfaces import IOverviewGroupMovedEvent
from nti.contenttypes.presentation.interfaces import IPresentationAssetMovedEvent
from nti.contenttypes.presentation.interfaces import IWillUpdatePresentationAssetEvent

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTIDocketAsset
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IItemAssetContainer
from nti.contenttypes.presentation.interfaces import IUserCreatedTranscript
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import IPresentationAssetCreatedEvent
from nti.contenttypes.presentation.interfaces import IWillRemovePresentationAssetEvent
from nti.contenttypes.presentation.interfaces import ItemRemovedFromItemAssetContainerEvent
from nti.contenttypes.presentation.interfaces import IItemRemovedFromItemAssetContainerEvent

from nti.coremetadata.utils import current_principal as core_current_principal

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IObjectModifiedFromExternalEvent

from nti.externalization.oids import to_external_ntiid_oid

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.interfaces import TRX_TYPE_CREATE

from nti.recorder.interfaces import IRecordable

from nti.recorder.record import remove_transaction_history

from nti.recorder.utils import record_transaction

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS

# interaction


def current_principal():
    return core_current_principal(False)


# courses


def _get_course_sync_results(event):
    result = None
    sync_results = event.results
    if sync_results is not None and sync_results.Items:
        result = sync_results.Items[-1]
    return result


@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _on_course_instance_available(course, event):
    catalog = get_library_catalog()
    if catalog is not None and not ILegacyCourseInstance.providedBy(course):
        sync_results = _get_course_sync_results(event)
        synchronize_course_lesson_overview(course,
                                           catalog=catalog,
                                           sync_results=sync_results)


@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _clear_data_when_course_removed(course, event):
    catalog = get_library_catalog()
    if catalog is None or ILegacyCourseInstance.providedBy(course):
        return

    # clear containers
    clear_course_assets(course)
    clear_namespace_last_modified(course, catalog)

    # unregister assets
    entry = ICourseCatalogEntry(course, None)
    ntiid = entry.ntiid if entry is not None else course.__name__
    removed = remove_and_unindex_course_assets(container_ntiids=ntiid,
                                               catalog=catalog,
                                               course=course,
                                               force=True)

    # remove transactions
    for item in removed:
        remove_transaction_history(item)

# Outline nodes


@component.adapter(ICourseOutlineNode, IUnregistered)
def _on_outlinenode_unregistered(node, event):
    lesson = INTILessonOverview(node, None)
    if lesson is None:
        return

    # ground lesson
    lesson.__parent__ = None

    # unregister empty lesson overviews to avoid leaking
    registry = get_site_registry()
    if not lesson.Items and registry != component.getGlobalSiteManager():
        remove_presentation_asset(lesson, registry)

# Presentation assets


@component.adapter(INTICourseOverviewGroup, IWillRemovePresentationAssetEvent)
def _on_will_remove_course_overview_group(group, event):
    lesson = group.__parent__
    if INTILessonOverview.providedBy(lesson):
        lesson.remove(group)


@component.adapter(IItemAssetContainer, IItemRemovedFromItemAssetContainerEvent)
def _on_item_asset_containter_modified(container, event):
    principal = current_principal()
    if principal is not None and IRecordable.providedBy(container):
        record_transaction(container, principal=principal, descriptions=(ITEMS,),
                           type_=TRX_ASSET_REMOVED_FROM_ITEM_ASSET_CONTAINER)


@component.adapter(IPresentationAsset, IPresentationAssetCreatedEvent)
def _on_presentation_asset_created(asset, event):
    if IRecordable.providedBy(asset) and event.principal:
        record_transaction(asset,
                           principal=event.principal,
                           type_=TRX_TYPE_CREATE)


@component.adapter(INTICourseOverviewGroup, IOverviewGroupMovedEvent)
def _on_group_moved(group, event):
    ntiid = getattr(group, 'ntiid', None)
    if ntiid:
        record_transaction(group, principal=event.principal,
                           type_=TRX_OVERVIEW_GROUP_MOVE_TYPE)


@component.adapter(IPresentationAsset, IPresentationAssetMovedEvent)
def _on_asset_moved(asset, event):
    ntiid = getattr(asset, 'ntiid', None)
    # Update our index. IPresentationAssets are the only movable
    # entity that needs to update its index containers.
    # If no old_parent_ntiid, it was an internal move.
    if event.old_parent_ntiid:
        catalog = get_library_catalog()
        catalog.remove_containers(asset, event.old_parent_ntiid)
        catalog.update_containers(asset, asset.__parent__.ntiid)
    if ntiid and IRecordable.providedBy(asset):
        record_transaction(asset, principal=event.principal,
                           type_=TRX_ASSET_MOVE_TYPE)


@component.adapter(IPresentationAsset, IIntIdAddedEvent)
def _on_asset_registered(asset, event):
    if queryInteraction() is not None:
        interface.alsoProvides(asset, IUserCreatedAsset)


@component.adapter(IPresentationAsset, IObjectModifiedFromExternalEvent)
def _on_asset_modified(asset, event):
    if current_principal() is not None:
        catalog = get_library_catalog()
        containers = catalog.get_containers(asset)
        for ntiid in containers or ():
            obj = find_object_with_ntiid(ntiid)
            if INTILessonOverview.providedBy(obj):
                obj.lock()  # lesson


@component.adapter(IPresentationAsset, IWillRemovePresentationAssetEvent)
def _on_will_remove_presentation_asset(asset, event):
    # remove from containers
    for context in get_presentation_asset_containers(asset):
        if ICourseInstance.providedBy(context):
            containers = chain((context,), get_course_packages(context))
        else:
            containers = (context,)
        for container in containers:
            if IItemAssetContainer.providedBy(container) and container.remove(asset):
                # XXX: notify the item asset container has been modified
                notify(ItemRemovedFromItemAssetContainerEvent(container, asset))
            else:
                mapping = IPresentationAssetContainer(container, None)
                if mapping is not None:
                    mapping.pop(asset.ntiid, None)


@component.adapter(INTIDocketAsset, IWillUpdatePresentationAssetEvent)
def _on_will_update_presentation_asset(asset, event):
    externalValue = event.externalValue or {}
    for name in ('href', 'icon'):
        if name in externalValue:
            value = getattr(asset, name, None)
            if value and is_internal_file_link(value):
                source = get_file_from_external_link(value)
                if IContentBaseFile.providedBy(source):
                    source.remove_association(asset)
                    lifecycleevent.modified(source)


@component.adapter(INTIDocketAsset, IBeforeIdRemovedEvent)
def _on_docket_asset_removed(asset, event):
    for name in ('href', 'icon'):
        value = getattr(asset, name, None)
        if value and is_internal_file_link(value):
            source = get_file_from_external_link(value)
            if IContentBaseFile.providedBy(source):
                source.remove_association(asset)
                lifecycleevent.modified(source)


@component.adapter(INTICourseOverviewGroup, IAfterIdAddedEvent)
def _on_course_overview_registered(group, event):
    # TODO: Execute only if there is an interaction
    parent = group.__parent__
    catalog = get_library_catalog()
    extended = (group.ntiid, getattr(parent, 'ntiid', None))
    for item in group or ():
        concrete = IConcreteAsset(item, item)
        for asset in {concrete, item}:
            catalog.update_containers(asset, extended)


@component.adapter(INTICourseOverviewGroup, IObjectModifiedEvent)
def _on_course_overview_modified(group, event):
    _on_course_overview_registered(group, None)


@component.adapter(IContentBaseFile, IBeforeIdRemovedEvent)
def _on_content_file_removed(context, event):
    if not context.has_associations():
        return
    oid = to_external_ntiid_oid(context)
    href = to_external_file_link(context)
    for obj in context.associations():
        if INTIDocketAsset.providedBy(obj):
            if obj.target == oid or obj.href == href:
                if INTIRelatedWorkRef.providedBy(obj):
                    obj.type = None
                obj.target = obj.href = None
            else:  # refers to icon
                obj.icon = None


@component.adapter(IQAssignment, IBeforeIdRemovedEvent)
def _on_assignment_removed(assignment, event):
    """
    Remove deleted assignment from all overview groups referencing it.
    """
    count = 0
    ntiid = getattr(assignment, 'ntiid', None)
    courses = get_evaluation_courses(assignment)
    registry = get_site_registry()
    if     not ntiid \
        or not courses \
        or current_principal() is None \
        or registry == component.getGlobalSiteManager():
        return

    # Get all overview groups for course.
    container_ntiids = [ICourseCatalogEntry(x).ntiid for x in courses]
    catalog = get_library_catalog()
    sites = get_component_hierarchy_names()
    groups = tuple(catalog.search_objects(provided=INTICourseOverviewGroup,
                                          container_ntiids=container_ntiids,
                                          container_all_of=False,
                                          sites=sites))
    for group in groups:
        for item in tuple(group):
            if      INTIAssignmentRef.providedBy(item) \
                and assignment.ntiid == getattr(item, 'target', ''):
                # This ends up removing from group here.
                remove_presentation_asset(item, registry)
                count += 1
    if count:
        logger.info('Removed assignment (%s) from %s overview group(s)',
                    ntiid, count)


@component.adapter(INTIMedia, IBeforeIdRemovedEvent)
def _on_media_removed(media, _):
    """
    Notify removal of user created transcripts
    """
    for transcript in getattr(media ,'transcripts', None) or ():
        if IUserCreatedTranscript.providedBy(transcript):
            lifecycleevent.removed(transcript)


@component.adapter(IQEvaluation, IObjectModifiedEvent)
def _on_evaluation_modified(evaluation, event):
    ntiid = getattr(evaluation, 'ntiid', None)
    course = find_interface(evaluation, ICourseInstance, strict=False)
    if not ntiid \
        or course is None \
        or current_principal() is None \
        or not IQEditableEvaluation.providedBy(evaluation) \
        or not (IQAssignment.providedBy(evaluation)
                or IQuestionSet.providedBy(evaluation)):
        return

    # Get all item refs for course.
    catalog = get_library_catalog()
    sites = get_component_hierarchy_names()
    ntiid = ICourseCatalogEntry(course).ntiid

    # update question counts
    provided = (INTIAssignmentRef, INTIQuestionSetRef,
                INTISurveyRef, INTIPollRef)
    items = catalog.search_objects(provided=provided,
                                   container_ntiids=ntiid,
                                   sites=sites)
    for item in items or ():
        target = getattr(item, 'target', '')
        if target == ntiid:
            item.title = evaluation.title or item.title
            if     INTIQuestionSetRef.providedBy(item) \
                or INTISurveyRef.providedBy(item):
                item.question_count = getattr(evaluation, 'draw', None) \
                                   or len(evaluation.questions or ())


@component.adapter(IContentUnit)
@interface.implementer(IContentUnitAssociations)
class _RelatedWorkRefContentUnitAssociations(object):

    def __init__(self, *args):
        pass

    def associations(self, context):
        return get_content_related_work_refs(context)


def _get_ref_pointers(ref):
    """
    For a related work ref, find all pointers to it.
    """
    catalog = get_library_catalog()
    sites = get_component_hierarchy_names()
    pointers = tuple(catalog.search_objects(provided=INTIRelatedWorkRefPointer,
                                            target=ref.ntiid,
                                            sites=sites))
    return pointers


@component.adapter(IContentUnit, IContentUnitRemovedEvent)
def _on_content_removed(unit, event):
    """
    Remove related work refs pointing to deleted content.
    XXX: This must be a content removed event because
    we may churn intids during re-renders.
    """
    refs = get_content_related_work_refs(unit)
    for ref in refs or ():
        ref_ntiid = ref.ntiid
        # Must get these before deleting ref.
        pointers = _get_ref_pointers(ref)
        # This ends up removing from group here.
        remove_presentation_asset(ref)
        for pointer in pointers:
            remove_presentation_asset(pointer)
        logger.info('Removed related work ref (%s) on content deletion (%s) (pointers=%s)',
                    ref_ntiid,
                    unit.ntiid,
                    len(pointers))


def _get_content_units_for_package(package):
    result = []
    def _recur(unit):
        result.append(unit)
        for child in unit.children or ():
            _recur(child)
    _recur(package)
    return result


@component.adapter(IContentPackage, IContentPackageRemovedEvent)
def _on_package_removed(package, event):
    """
    Remove related work refs pointing to deleted content.
    XXX: This must be a content package removed event because
    we may churn intids during re-renders.
    """
    logger.info('Removed related work refs on package deletion (%s)',
                package.ntiid)
    # XXX: Do we need to do unit, or can we just do by package?
    units = _get_content_units_for_package(package)
    for unit in units:
        _on_content_removed(unit, event)


@component.adapter(ICourseInstance, ICourseBundleUpdatedEvent)
def update_course_asset_containers(course, event):
    """
    When a package is removed from a bundle, we need to remove any
    reference to our course in the asset containers.
    synchronizer.py handles linking package assets to our course.
    """
    for package_ntiid in event.removed_packages or ():
        remove_package_assets_from_course_container(package_ntiid, course)
