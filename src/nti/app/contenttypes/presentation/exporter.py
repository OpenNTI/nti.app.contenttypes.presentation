#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from zope import interface
from zope import component

from nti.app.contenttypes.presentation.interfaces import ILessonOverviewsSectionExporter

from nti.app.contenttypes.presentation.utils.course import course_discussions

from nti.app.products.courseware.utils.exporter import save_resources_to_filer

from nti.assessment.interfaces import IQEvaluation
from nti.assessment.interfaces import IQEditableEvaluation

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IEditableContentUnit

from nti.contenttypes.courses.discussions.exporter import user_topic_file_name
from nti.contenttypes.courses.discussions.exporter import user_topic_dicussion_id
from nti.contenttypes.courses.discussions.exporter import export_user_topic_as_discussion

from nti.contenttypes.courses.discussions.parser import path_to_discussions

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussionTopic
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussionsSectionExporter

from nti.contenttypes.courses.exporter import BaseSectionExporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSectionExporter
from nti.contenttypes.courses.interfaces import ICourseSectionExporterExecutedEvent

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import PUBLICATION_CONSTRAINTS

from nti.contenttypes.presentation import interface_of_asset

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IItemAssetContainer
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import ISurveyCompletionConstraint
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraints
from nti.contenttypes.presentation.interfaces import IAssignmentCompletionConstraint
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.dataserver.contenttypes.forums.interfaces import ITopic
from nti.dataserver.contenttypes.forums.interfaces import IHeadlinePost

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

from nti.mimetype.externalization import decorateMimeType

from nti.namedfile.file import safe_filename

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import is_ntiid_of_types
from nti.ntiids.ntiids import is_valid_ntiid_string 
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

ID = StandardExternalFields.ID
OID = StandardExternalFields.OID
ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
INTERNAL_NTIID = StandardInternalFields.NTIID
CONTAINER_ID = StandardExternalFields.CONTAINER_ID
INTERNAL_CONTAINER_ID = StandardInternalFields.CONTAINER_ID


def _outline_nodes(outline, seen):
    result = []
    def _recur(node):
        ntiid = node.LessonOverviewNTIID
        if ntiid and ntiid not in seen:
            seen.add(ntiid)
            lesson = find_object_with_ntiid(ntiid)
            if lesson is not None:
                result.append((node, lesson))
        # parse children
        for child in node.values():
            _recur(child)
    if outline is not None:
        _recur(outline)
    return result


class AssetExporterMixin(object):

    def __init__(self, *args, **kwargs):
        super(AssetExporterMixin, self).__init__(*args, **kwargs)

    def _post_process_asset(self, asset, ext_obj, filer, backup=True, salt=None):
        concrete = IConcreteAsset(asset, asset)
        provided = interface_of_asset(concrete)
        # remove identifying data if not backup mode
        [ext_obj.pop(x, None) for x in (OID, CONTAINER_ID)]
        if not backup:  # remove unrequired keys
            if not INTIDiscussionRef.providedBy(asset):
                ext_obj.pop(ID, None)
            elif asset.isCourseBundle():
                ext_obj.pop('target', None)
            if INTIAssessmentRef.providedBy(asset):
                ext_obj.pop(INTERNAL_CONTAINER_ID, None)
            if INTIMediaRoll.providedBy(asset.__parent__):
                [ext_obj.pop(x, None) for x in (NTIID, INTERNAL_NTIID)]
            if      INTIMedia.providedBy(concrete) \
                and not INTIMediaRoll.providedBy(asset.__parent__):
                # XXX: Why not items in media rolls?
                for name in ('sources', 'transcripts'):
                    for item in ext_obj.get(name) or ():
                        [item.pop(x, None) for x in (OID, NTIID, INTERNAL_NTIID)]

                if IUserCreatedAsset.providedBy(concrete):
                    # Update our ntiid so video refs line up correctly.
                    new_ntiid = self.hash_ntiid(asset.ntiid, salt)
                    ext_obj[NTIID] = ext_obj[INTERNAL_NTIID] = new_ntiid
            # If not user created and not a package asset, we always
            # want to pop the ntiid to avoid ntiid collision (except for
            # user created media).
            elif not IContentBackedPresentationAsset.providedBy(concrete):
                [ext_obj.pop(x, None) for x in (NTIID, INTERNAL_NTIID)]
        # check for user discussions
        if INTIDiscussionRef.providedBy(asset):
            if is_valid_ntiid_string(asset.target or ''):
                target = find_object_with_ntiid(asset.target)
                if IHeadlinePost.providedBy(target):
                    target = target.__parent__
                if ITopic.providedBy(target):
                    name = target.__name__ # by definition
                    course = find_interface(asset, ICourseInstance, strict=False)
                    discussions = course_discussions(course)
                    discussion = discussions.get(name)
                    if discussion is not None:
                        discussion_id = discussion.id
                    else:
                        discussion_id = user_topic_dicussion_id(target)
                    ext_obj[ID] = ext_obj['target'] = discussion_id
        # check 'children'
        if IItemAssetContainer.providedBy(asset):
            if INTISlideDeck.providedBy(asset):
                for name in ('Videos', 'Slides'):
                    ext_items = ext_obj.get(name) or ()
                    deck_items = getattr(asset, name, None) or ()
                    for item, item_ext in zip(deck_items, ext_items):
                        self._post_process_asset(asset=item,
                                                 ext_obj=item_ext,
                                                 filer=filer,
                                                 backup=backup,
                                                 salt=salt)
            else:
                ext_items = ext_obj.get(ITEMS) or ()
                asset_items = asset.Items if asset.Items is not None else ()
                for item, item_ext in zip(asset_items, ext_items):
                    if     not item_ext.get(NTIID) \
                        or not item_ext.get(INTERNAL_NTIID):  # check valid NTIID
                        item_ext.pop(NTIID, None)
                        item_ext.pop(INTERNAL_NTIID, None)
                    self._post_process_asset(asset=item,
                                             ext_obj=item_ext,
                                             filer=filer,
                                             backup=backup,
                                             salt=salt)
        if not backup:
            # check references to authored evaluations
            if      INTIAssessmentRef.providedBy(asset) \
                and IQEditableEvaluation.providedBy(IQEvaluation(asset, None)):
                ext_obj['target'] = self.hash_ntiid(asset.target, salt)
            # process lesson constraints
            elif    INTILessonOverview.providedBy(asset) \
                and PUBLICATION_CONSTRAINTS in ext_obj:
                self._post_lesson_constraints(asset, ext_obj, salt)
            # update related work refs targets
            elif INTIRelatedWorkRef.providedBy(concrete):
                target = find_object_with_ntiid(concrete.target)
                if IEditableContentUnit.providedBy(target):
                    for name in ('target', 'href'):
                        ext_obj[name] = self.hash_ntiid(concrete.target, salt)
            elif    INTIMediaRef.providedBy(asset) \
                and IUserCreatedAsset.providedBy(concrete):
                # We need to update our ref targets here
                ext_obj['target'] = self.hash_ntiid(asset.target, salt)
            # don't leak internal OIDs
            for name in (NTIID, INTERNAL_NTIID, INTERNAL_CONTAINER_ID, 'target'):
                value = ext_obj.get(name)
                if      value \
                    and is_ntiid_of_types(value, (TYPE_OID, TYPE_UUID)):
                    ext_obj.pop(name, None)
        # save asset/concrete resources
        save_resources_to_filer(provided, concrete, filer, ext_obj)


@interface.implementer(ILessonOverviewsSectionExporter)
class LessonOverviewsExporter(BaseSectionExporter, AssetExporterMixin):

    def _post_lesson_constraints(self, asset, ext_obj, salt=None):
        ext_constraints = ext_obj.get(PUBLICATION_CONSTRAINTS)
        constraints = ILessonPublicationConstraints(asset).Items
        if ext_constraints is not None:
            ext_items = ext_constraints.get(ITEMS)
            for ix, ext_constraint in enumerate(ext_items or ()):
                constraint = constraints[ix]
                if ISurveyCompletionConstraint.providedBy(constraint):
                    ntiids = ext_constraint.get('surveys')
                elif IAssignmentCompletionConstraint.providedBy(constraint):
                    ntiids = ext_constraint.get('assignments')
                else:
                    ntiids = ()
                for i, ntiid in enumerate(ntiids or ()):
                    evaluation = component.queryUtility(IQEvaluation, ntiid)
                    # only hash ntiid if it's an authored evaluation
                    if IQEditableEvaluation.providedBy(evaluation):
                        ntiids[i] = self.hash_ntiid(ntiids[i], salt)
                # remove ntiids
                ext_constraint.pop(NTIID, None)
                ext_constraint.pop(INTERNAL_NTIID, None)

    def _do_export(self, context, filer, seen, backup=True, salt=None):
        course = ICourseInstance(context)
        nodes = _outline_nodes(course.Outline, seen)
        for node, lesson in nodes:
            ext_obj = to_external_object(lesson,
                                         name="exporter",
                                         decorate=False)
            if not backup:
                ext_obj.pop("lesson", None)

            # process internal resources
            self._post_process_asset(lesson, ext_obj, filer, backup, salt)
            # save to json
            source = self.dump(ext_obj)
            # save to filer
            name = safe_filename(node.src or lesson.ntiid)
            name = name + '.json' if not name.endswith('.json') else name
            if not backup:  # hash source file
                name = self.hash_filename(name, salt)
            bucket = self.course_bucket(course) or ''
            filer.default_bucket = bucket = os.path.join(bucket, 'Lessons')
            filer.save(name, source,
                       overwrite=True,
                       bucket=bucket,
                       contentType="application/x-json")

    def export(self, context, filer, backup=True, salt=None):
        seen = set()
        course = ICourseInstance(context)
        self._do_export(context, filer, seen, backup, salt)
        for sub_instance in get_course_subinstances(course):
            if sub_instance.Outline != course.Outline:
                self._do_export(sub_instance, filer, seen, backup, salt)
        filer.default_bucket = None # restore


@interface.implementer(ICourseSectionExporter)
class UserAssetsExporter(BaseSectionExporter, AssetExporterMixin):

    def _iter_user_assets(self, course):
        # We only need to capture user created videos.
        # XXX: Concrete relatedworkrefs and timelines are internalized via
        # definitions in the lessons.
        container = IPresentationAssetContainer(course)
        for item in container.assets():
            if      INTIMedia.providedBy(item) \
                and IUserCreatedAsset.providedBy(item):
                yield item

    def _get_ext_user_assets(self, course, filer, seen, backup, salt):
        result = []
        for asset in self._iter_user_assets(course):
            if asset.ntiid in seen:
                continue
            seen.add(asset.ntiid)
            ext_obj = to_external_object(asset,
                                         name="exporter",
                                         decorate=False)
            decorateMimeType(asset, ext_obj)
            self._post_process_asset(asset, ext_obj, filer, backup, salt)
            result.append(ext_obj)
        return result

    def _export_assets(self, course, filer, seen, backup, salt):
        """
        Export user created assets. We'll store all parent/subinstance assets
        in a single file at the parent level.
        """
        ext_assets = self._get_ext_user_assets(course, filer, 
                                               seen, backup, salt)
        if ext_assets:
            source = self.dump(ext_assets)
            filer.default_bucket = bucket = self.course_bucket(course)
            filer.save('user_assets.json', source,
                       overwrite=True,
                       bucket=bucket,
                       contentType="application/x-json")
        return ext_assets

    def export(self, context, filer, backup=True, salt=None):
        seen = set()
        course = ICourseInstance(context)
        self._export_assets(course, filer, seen, backup, salt)
        for sub_instance in get_course_subinstances(course):
            if sub_instance.Outline != course.Outline:
                self._export_assets(sub_instance, filer, seen, backup, salt)
        filer.default_bucket = None # restore


def export_user_course_discussions(context, exporter, filer):
    result = []
    catalog = get_library_catalog()
    course = ICourseInstance(context)
    entry = ICourseCatalogEntry(course)
    bucket = path_to_discussions(course)
    for item in catalog.search_objects(provided=INTIDiscussionRef,
                                       container_ntiids=entry.ntiid,
                                       sites=get_component_hierarchy_names()):
        if not INTIDiscussionRef.providedBy(item):
            continue
        if not is_valid_ntiid_string(item.target or ''):
            continue
        context = find_object_with_ntiid(item.target)
        if IHeadlinePost.providedBy(context):
            context = context.__parent__
        if      ITopic.providedBy(context) \
            and not ICourseDiscussionTopic.providedBy(context):
            ext_obj = export_user_topic_as_discussion(context)
            source = exporter.dump(ext_obj)
            name = user_topic_file_name(context)
            filer.save(name, source, contentType="application/json",
                       bucket=bucket, overwrite=True)
            result.append(context)
    return result


@component.adapter(ICourseInstance, ICourseSectionExporterExecutedEvent)
def _on_course_section_exported_event(context, event):
    filer = event.filer
    exporter = event.exporter
    if ICourseDiscussionsSectionExporter.providedBy(exporter) and filer is not None:
        logger.info("Exporting lesson overviews course discussions")
        export_user_course_discussions(context, exporter, filer)
