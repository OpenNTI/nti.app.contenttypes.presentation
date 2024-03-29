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

from zope.component.hooks import getSite

from zope.interface.interfaces import IUnregistered

from zope.intid.interfaces import IIntIds
from zope.intid.interfaces import IIntIdAddedEvent

from zope.event import notify

from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from zope.security.management import queryInteraction

from zc.intid.interfaces import IAfterIdAddedEvent
from zc.intid.interfaces import IBeforeIdRemovedEvent

from nti.app.authentication import get_remote_user

from nti.app.contentfolder.resources import is_internal_file_link
from nti.app.contentfolder.resources import to_external_file_link
from nti.app.contentfolder.resources import get_file_from_external_link

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.synchronizer import clear_course_assets
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import remove_and_unindex_course_assets
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.contenttypes.presentation.utils import generate_node_ntiid

from nti.app.contenttypes.presentation.utils.asset import intid_register
from nti.app.contenttypes.presentation.utils.asset import remove_mediaroll
from nti.app.contenttypes.presentation.utils.asset import create_lesson_4_node
from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_containers
from nti.app.contenttypes.presentation.utils.course import remove_package_assets_from_course_container

from nti.app.products.courseware.utils import get_content_related_work_refs

from nti.assessment import IQSurvey

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
from nti.contentlibrary.interfaces import IRenderableContentPackage
from nti.contentlibrary.interfaces import IContentPackageRemovedEvent

from nti.contenttypes.calendar.interfaces import ICalendarEvent

from nti.contenttypes.completion.interfaces import ICompletableItem
from nti.contenttypes.completion.interfaces import IUserProgressUpdatedEvent

from nti.contenttypes.completion.utils import update_completion

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode
from nti.contenttypes.courses.interfaces import ICourseBundleUpdatedEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceRemovedEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceImportedEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceAvailableEvent
from nti.contenttypes.courses.interfaces import ICourseContentLibraryProvider
from nti.contenttypes.courses.interfaces import IDoNotCreateDefaultOutlineCourseInstance

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.outlines import CourseOutlineNode
from nti.contenttypes.courses.outlines import CourseOutlineContentNode

from nti.contenttypes.courses.utils import get_parent_course

from nti.contenttypes.presentation import NTI_LESSON_OVERVIEW

from nti.contenttypes.presentation.group import DuplicateReference
from nti.contenttypes.presentation.group import NTICourseOverViewGroup

from nti.contenttypes.presentation.index import IX_SITE
from nti.contenttypes.presentation.index import IX_CONTAINERS
from nti.contenttypes.presentation.index import get_assets_catalog

from nti.contenttypes.presentation.interfaces import TRX_ASSET_MOVE_TYPE
from nti.contenttypes.presentation.interfaces import TRX_OVERVIEW_GROUP_MOVE_TYPE
from nti.contenttypes.presentation.interfaces import TRX_ASSET_REMOVED_FROM_ITEM_ASSET_CONTAINER

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIAudioRef
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTIDocketAsset
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IItemAssetContainer
from nti.contenttypes.presentation.interfaces import INTICalendarEventRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IOverviewGroupMovedEvent
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import IPresentationAssetMovedEvent
from nti.contenttypes.presentation.interfaces import IPresentationAssetCreatedEvent
from nti.contenttypes.presentation.interfaces import IWillUpdatePresentationAssetEvent
from nti.contenttypes.presentation.interfaces import IWillRemovePresentationAssetEvent
from nti.contenttypes.presentation.interfaces import ItemRemovedFromItemAssetContainerEvent
from nti.contenttypes.presentation.interfaces import IItemRemovedFromItemAssetContainerEvent

from nti.contenttypes.presentation.lesson import constraints_for_lesson

from nti.contenttypes.presentation.media import NTIVideo

from nti.contenttypes.presentation.relatedwork import NTIRelatedWorkRef

from nti.contenttypes.presentation.timeline import NTITimeLine

from nti.coremetadata.interfaces import IUser

from nti.coremetadata.utils import current_principal as core_current_principal

from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IObjectModifiedFromExternalEvent

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

from nti.recorder.interfaces import TRX_TYPE_CREATE

from nti.recorder.interfaces import IRecordable

from nti.recorder.record import remove_transaction_history

from nti.recorder.utils import record_transaction

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility

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
def _clear_data_when_course_removed(course, unused_event):
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


def _package_assets(package):
    result = set()
    def recur(unit):
        for child in unit.children or ():
            recur(child)
        container = IPresentationAssetContainer(unit)
        # pylint: disable=too-many-function-args
        result.update(container.assets())
    recur(package)
    return result


@component.adapter(ICourseInstance, ICourseInstanceImportedEvent)
def _on_course_instance_imported(course, unused_event):
    entry = ICourseCatalogEntry(course)
    assets_catalog = get_assets_catalog()
    library_catalog = get_library_catalog()
    intids = component.getUtility(IIntIds)
    for package in get_course_packages(course):
        # ignore authored packages
        if IRenderableContentPackage.providedBy(package):
            continue
        # update containers for the unit assets
        # to mark the new course
        for asset in _package_assets(package):
            if assets_catalog is not None:
                assets_catalog.update_containers(asset, (entry.ntiid,), intids)
            if library_catalog is not None:
                library_catalog.update_containers(asset, (entry.ntiid,), intids)


# Outline nodes


@component.adapter(ICourseOutlineNode, IUnregistered)
def _on_outlinenode_unregistered(node, unused_event):
    course = find_interface(node, ICourseInstance, strict=False)
    folder = IHostPolicyFolder(course, None)
    lesson = INTILessonOverview(node, None)
    if lesson is None:
        return
    # ground lesson
    lesson.__parent__ = None
    # unregister empty lesson overviews to avoid leaking
    # pylint: disable=too-many-function-args
    registry = get_site_registry() if folder is None else folder.getSiteManager()
    if not lesson.Items and registry != component.getGlobalSiteManager():
        remove_presentation_asset(lesson, registry)


# Presentation assets


@component.adapter(INTICourseOverviewGroup, IWillRemovePresentationAssetEvent)
def _on_will_remove_course_overview_group(group, unused_event):
    lesson = group.__parent__
    if INTILessonOverview.providedBy(lesson):
        lesson.remove(group)


@component.adapter(IItemAssetContainer, IItemRemovedFromItemAssetContainerEvent)
def _on_item_asset_containter_modified(container, unused_event):
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
def _on_asset_registered(asset, unused_event):
    if queryInteraction() is not None:
        interface.alsoProvides(asset, IUserCreatedAsset)


@component.adapter(IPresentationAsset, IObjectModifiedFromExternalEvent)
def _on_asset_modified(asset, unused_event):
    if current_principal() is not None:
        catalog = get_library_catalog()
        containers = catalog.get_containers(asset)
        for ntiid in containers or ():
            obj = find_object_with_ntiid(ntiid)
            if INTILessonOverview.providedBy(obj):
                obj.lock()  # lesson


@component.adapter(IPresentationAsset, IWillRemovePresentationAssetEvent)
def _on_will_remove_presentation_asset(asset, unused_event):
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
def _on_docket_asset_removed(asset, unused_event):
    for name in ('href', 'icon'):
        value = getattr(asset, name, None)
        if value and is_internal_file_link(value):
            source = get_file_from_external_link(value)
            if IContentBaseFile.providedBy(source):
                source.remove_association(asset)
                lifecycleevent.modified(source)


@component.adapter(INTICourseOverviewGroup, IAfterIdAddedEvent)
def _on_course_overview_registered(group, unused_event):
    # TODO: Execute only if there is an interaction
    parent = group.__parent__
    catalog = get_library_catalog()
    extended = (group.ntiid, getattr(parent, 'ntiid', None))
    for item in group or ():
        concrete = IConcreteAsset(item, item)
        for asset in {concrete, item}:
            catalog.update_containers(asset, extended)


@component.adapter(INTICourseOverviewGroup, IObjectModifiedEvent)
def _on_course_overview_modified(group, unused_event):
    _on_course_overview_registered(group, None)


@component.adapter(INTILessonOverview, IBeforeIdRemovedEvent)
def _on_lesson_removed(lesson, unused_event=None):
    constraints = constraints_for_lesson(lesson, False)
    if constraints:
        constraints.clear()


@component.adapter(IContentBaseFile, IBeforeIdRemovedEvent)
def _on_content_file_removed(context, unused_event):
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


def _on_target_removed(context, iface):
    count = 0
    ntiid = getattr(context, 'ntiid', None)
    registry = get_site_registry()
    if     not ntiid \
        or current_principal() is None \
        or not IQEditableEvaluation.providedBy(context) \
        or registry == component.getGlobalSiteManager():
        return count

    catalog = get_library_catalog()
    sites = get_component_hierarchy_names()
    items = catalog.search_objects(provided=iface,
                                   target=ntiid,
                                   sites=sites)

    for item in items or ():
        if      iface.providedBy(item) \
            and context.ntiid == getattr(item, 'target', ''):
            # This ends up removing from containers.
            remove_presentation_asset(item, registry)
            count += 1

    return count


@component.adapter(IQAssignment, IBeforeIdRemovedEvent)
def _on_assignment_removed(assignment, unused_event):
    """
    Remove deleted (editable) assignment from all overview groups referencing
    it.
    """
    count = _on_target_removed(assignment, INTIAssignmentRef)
    if count:
        logger.info('Removed assignment (%s) from %s overview group(s)',
                    getattr(assignment, 'ntiid', None), count)
    return count


@component.adapter(IQSurvey, IBeforeIdRemovedEvent)
def _on_survey_removed(survey, unused_event):
    """
    Remove deleted (editable) survey from all overview groups referencing
    it.
    """
    count = _on_target_removed(survey, INTISurveyRef)
    if count:
        logger.info('Removed survey (%s) from %s overview group(s)',
                    getattr(survey, 'ntiid', None), count)
    return count


@component.adapter(IQEvaluation, IObjectModifiedEvent)
def _on_evaluation_modified(evaluation, unused_event):
    eval_ntiid = getattr(evaluation, 'ntiid', None)
    course = find_interface(evaluation, ICourseInstance, strict=False)
    if not eval_ntiid \
        or course is None \
        or current_principal() is None \
        or not IQEditableEvaluation.providedBy(evaluation) \
        or not (IQAssignment.providedBy(evaluation)
                or IQuestionSet.providedBy(evaluation)
                or IQSurvey.providedBy(evaluation)):
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
        if target == eval_ntiid:
            item.title = evaluation.title or item.title
            if     INTIQuestionSetRef.providedBy(item) \
                or INTISurveyRef.providedBy(item):
                item.question_count = getattr(evaluation, 'draw', None) \
                                   or len(evaluation.questions or ())


@component.adapter(ICalendarEvent, IBeforeIdRemovedEvent)
def _on_calendar_event_removed(calendar_event, unused_event):
    """
    Remove deleted calendar events from all overview groups referencing it.
    """
    count = 0
    ntiid = getattr(calendar_event, 'ntiid', None)
    registry = get_site_registry()
    if     not ntiid \
        or current_principal() is None \
        or registry == component.getGlobalSiteManager():
        return count

    catalog = get_library_catalog()
    sites = get_component_hierarchy_names()
    items = catalog.search_objects(provided=INTICalendarEventRef,
                                   target=ntiid,
                                   sites=sites)
    for item in items or ():
        if      INTICalendarEventRef.providedBy(item) \
            and calendar_event.ntiid == getattr(item, 'target', ''):
            # This ends up removing from containers.
            remove_presentation_asset(item, registry)
            count += 1
    if count:
        logger.info('Removed calendar event (%s) from %s overview group(s)', ntiid, count)
    return count


@component.adapter(IContentUnit)
@interface.implementer(IContentUnitAssociations)
class _RelatedWorkRefContentUnitAssociations(object):

    def __init__(self, *args):
        pass

    def associations(self, context):
        return get_content_related_work_refs(context)


def _get_target_refs(target_ntiid, provided_interface):
    """
    For a target_ntiid and interface, get all references.
    """
    catalog = get_library_catalog()
    sites = get_component_hierarchy_names()
    pointers = tuple(catalog.search_objects(provided=provided_interface,
                                            target=target_ntiid,
                                            sites=sites))
    return pointers


def _get_ref_pointers(ref):
    """
    For a related work ref, find all pointers to it.
    """
    return _get_target_refs(ref.ntiid, INTIRelatedWorkRefPointer)


@component.adapter(ITopic, IBeforeIdRemovedEvent)
def _on_topic_removed(topic, unused_event):
    """
    When an :class:`ITopic` is deleted, clean up any refs pointing to it.
    """
    pointers = _get_target_refs(topic.NTIID, INTIDiscussionRef)
    for pointer in pointers:
        remove_presentation_asset(pointer)


def _remove_media_pointers(media, iface):
    """
    Remove lesson pointers (iface) pointing to a given media type.
    """
    pointers = _get_target_refs(media.ntiid, iface)
    media_rolls = set()
    for pointer in pointers:
        if INTIMediaRoll.providedBy(pointer.__parent__):
            media_rolls.add(pointer.__parent__)
        remove_presentation_asset(pointer)
    for media_roll in media_rolls:
        # Remove containing video roll if necessary; mimics what the client does
        if len(media_roll) == 0:
            remove_mediaroll(media_roll)
        elif len(media_roll) == 1:
            group = find_interface(media_roll,
                                   INTICourseOverviewGroup,
                                   strict=False)
            if group is not None:
                insert_index = None
                for idx, item in enumerate(group):
                    if item == media_roll:
                        insert_index = idx
                        break
                if insert_index is not None:
                    try:
                        group.insert(insert_index, media_roll[0])
                    except DuplicateReference:
                        remove_mediaroll(media_roll)
                    else:
                        remove_mediaroll(media_roll, remove_video_refs=False)


@component.adapter(INTIVideo, IBeforeIdRemovedEvent)
def _on_video_removed(video, unused_event):
    """
     When an :class:`INTIVideo` is deleted, clean up any refs pointing to it.
    """
    if IUserCreatedAsset.providedBy(video):
        _remove_media_pointers(video, INTIVideoRef)


@component.adapter(INTIAudio, IBeforeIdRemovedEvent)
def _on_audio_removed(audio, unused_event):
    """
     When an :class:`INTIAudio` is deleted, clean up any refs pointing to it.
    """
    if IUserCreatedAsset.providedBy(audio):
        _remove_media_pointers(audio, INTIAudioRef)


@component.adapter(IContentUnit, IContentUnitRemovedEvent)
def _on_content_removed(unit, unused_event):
    """
    Remove related work refs pointing to deleted content.
    XXX: This must be a content removed event because we may churn intids
    during re-renders.
    """
    # This get's all refs to the given unit (why don't we
    # make this event listen for package removal?).
    refs = get_content_related_work_refs(unit)
    for ref in refs or ():
        # If the ref is not pointing to the removed unit, ignore.
        if ref.target != unit.ntiid:
            continue
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


def get_content_units_for_package(package):
    result = []
    def _recur(unit):
        result.append(unit)
        for child in unit.children or ():
            _recur(child)
    _recur(package)
    return result
_get_content_units_for_package = get_content_units_for_package


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
    units = get_content_units_for_package(package)
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


def unindex_course_assets(course, entry=None, site=None):
    catalog = get_assets_catalog()
    site = getSite() if site is None else site
    entry = ICourseCatalogEntry(course) if entry is None else entry
    if catalog is not None and site is not None:
        query = {
            IX_CONTAINERS: {'any_of': (entry.ntiid,)},
            IX_SITE: {'any_of': (site.__name__,)},
        }
        for uid in catalog.apply(query) or ():
            catalog.unindex_doc(uid)


@component.adapter(ICourseInstance, ICourseInstanceRemovedEvent)
def _on_course_instance_removed(course, event):
    unindex_course_assets(course, event.entry, event.site)


@component.adapter(IPresentationAsset, IUserProgressUpdatedEvent)
def _asset_progress(asset, event):
    """
    On asset progress update, update completion.
    """
    if ICompletableItem.providedBy(asset):
        update_completion(asset,
                          asset.ntiid,
                          event.user,
                          event.context)


@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _course_default_outline(course, unused_event):
    """
    On a valid new course, build out a default outline template. This
    should leave all publishable items published.

    XXX: This replicates a lot of work from outline and asset views.
    """
    if IDoNotCreateDefaultOutlineCourseInstance.providedBy(course):
        return
    parent_course = get_parent_course(course)
    # Do not want to duplicate default outline content for shared outlines.
    if      parent_course != course \
        and course.Outline == parent_course.Outline:
        return
    outline = course.Outline
    catalog_entry = ICourseCatalogEntry(course)
    remote_user = get_remote_user()
    folder = find_interface(course, IHostPolicyFolder)
    if folder is None:
        # Community course
        logger.debug('Course without host policy folder in lineage (%s) (%s)',
                     catalog_entry.ntiid, course.__parent__.__parent__)
        return
    registry = folder.getSiteManager()

    # Unit node
    unit_node = CourseOutlineNode()
    unit_node.title = _(u'Unit 1')
    unit_ntiid = generate_node_ntiid(outline,
                                     catalog_entry,
                                     remote_user)
    unit_node.ntiid = unit_ntiid
    registerUtility(registry,
                    component=unit_node,
                    name=unit_ntiid,
                    provided=ICourseOutlineNode)

    outline.insert(0, unit_node)
    outline.child_order_locked = True
    unit_node.locked = True
    unit_node.publish()

    # Lesson node
    lesson_node = CourseOutlineContentNode()
    lesson_node.title = _(u'Lesson 1')
    lesson_node_ntiid = generate_node_ntiid(unit_node,
                                            catalog_entry,
                                            remote_user)
    lesson_node.ntiid = lesson_node_ntiid
    registerUtility(registry,
                    component=lesson_node,
                    name=lesson_node_ntiid,
                    provided=ICourseOutlineContentNode)
    unit_node.insert(0, lesson_node)
    lesson_node.publish()

    # Create lesson
    lesson_ntiid = make_ntiid(nttype=NTI_LESSON_OVERVIEW,
                              base=lesson_node.ntiid)
    lesson = create_lesson_4_node(lesson_node,
                                  ntiid=lesson_ntiid,
                                  registry=registry,
                                  sites=folder.__name__)
    unit_node.child_order_locked = True
    lesson_node.locked = True
    lesson.locked = True
    lesson.publish()

    # Group (section)
    group = NTICourseOverViewGroup()
    group.creator = remote_user.username
    group.__parent__ = lesson
    group.title = _(u'Section 1')
    group.accentColor = u"F9824E"
    processor = IPresentationAssetProcessor(group)
    processor.handle(group, course)
    registerUtility(registry,
                    component=group,
                    name=group.ntiid,
                    provided=INTICourseOverviewGroup)
    intid_register(group, registry)
    lesson.insert(0, group)
    lesson.child_order_locked = True

    # container_ntiids and namespace should line up with
    # _handle_overview_group in the nti.app.contenttypes.presentation.views.asset_views.py.
    container_ntiids = (lesson.ntiid, catalog_entry.ntiid)
    namespace = to_external_ntiid_oid(lesson)
    catalog = get_library_catalog()
    catalog.index(group,
                  container_ntiids=container_ntiids,
                  namespace=namespace,
                  sites=folder.__name__)


@component.adapter(IUser, ICourseInstance)
@interface.implementer(ICourseContentLibraryProvider)
class _CourseContentLibraryProvider(object):
    """
    Return the mimetypes of objects of course content that could be
    added to this course by this user.
    """

    def __init__(self, user, course):
        self.user = user
        self.course = course

    def pkg_containers(self, package):
        result = []
        def recur(unit):
            for child in unit.children or ():
                recur(child)
            result.append(unit.ntiid)
        recur(package)
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

    def has_timelines(self):
        catalog = get_library_catalog()
        intids = component.getUtility(IIntIds)
        container_ntiids = self.course_containers(self.course)
        return tuple(catalog.search_objects(intids=intids,
                                            container_all_of=False,
                                            container_ntiids=container_ntiids,
                                            sites=get_component_hierarchy_names(),
                                            provided=(INTITimeline,)))

    def get_item_mime_types(self):
        """
        Returns the collection of mimetypes that may be available (either
        they exist or can exist) in this course.
        """
        result = [NTIVideo.mime_type,
                  NTIRelatedWorkRef.mime_type]
        if self.has_timelines():
            result.append(NTITimeLine.mime_type)
        return result
