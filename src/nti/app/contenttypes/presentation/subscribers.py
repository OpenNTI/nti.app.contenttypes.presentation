#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from itertools import chain

from zope import component

from zope.interface.interfaces import IUnregistered

from zope.event import notify

from zope.lifecycleevent import IObjectRemovedEvent

from zope.security.interfaces import NoInteraction
from zope.security.management import getInteraction

from ZODB.utils import serial_repr

from nti.coremetadata.interfaces import IRecordable

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import	ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceAvailableEvent

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation.interfaces import TRX_ASSET_REMOVED_FROM_ITEM_ASSET_CONTAINER

from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IItemAssetContainer
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import IWillRemovePresentationAssetEvent
from nti.contenttypes.presentation.interfaces import ItemRemovedFromItemAssetContainerEvent
from nti.contenttypes.presentation.interfaces import IItemRemovedFromItemAssetContainerEvent

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import append_records
from nti.recorder.record import TransactionRecord
from nti.recorder.record import remove_transaction_history

from .utils import get_course_packages
from .utils import get_presentation_asset_containers

from .synchronizer import clear_course_assets
from .synchronizer import clear_namespace_last_modified
from .synchronizer import remove_and_unindex_course_assets
from .synchronizer import synchronize_course_lesson_overview

# interaction

def principal():
	try:
		return getInteraction().participations[0].principal
	except (NoInteraction, IndexError, AttributeError):
		return None

# courses

@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _on_course_instance_available(course, event):
	catalog = get_library_catalog()
	if catalog is not None and not ILegacyCourseInstance.providedBy(course):
		synchronize_course_lesson_overview(course, catalog=catalog)

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
	if hasattr(node, 'LessonOverviewNTIID'):
		lesson = find_object_with_ntiid(node.LessonOverviewNTIID)
		if lesson is not None:
			lesson.__parent__ = None
			logger.warn("%s is an orphan lesson overview object", lesson.ntiid)

# Presentation assets

@component.adapter(INTICourseOverviewGroup, IWillRemovePresentationAssetEvent)
def _on_will_remove_course_overview_group(group, event):
	lesson = group.__parent__
	if INTILessonOverview.providedBy(lesson):
		lesson.remove(group)

@component.adapter(IItemAssetContainer, IItemRemovedFromItemAssetContainerEvent)
def _on_item_asset_containter_modified(container, event):
	principal = principal()
	if principal is not None and IRecordable.providedBy(container):
		tid = getattr(container, '_p_serial', None)
		tid = unicode(serial_repr(tid)) if tid else None
		record = TransactionRecord(type=TRX_ASSET_REMOVED_FROM_ITEM_ASSET_CONTAINER,
								   principal=principal.id,
								   tid=tid)
		append_records(container, (record,))
		container.locked = True

@component.adapter(IPresentationAsset, IWillRemovePresentationAssetEvent)
def _on_will_remove_presentation_asset(asset, event):
	# remove from containers
	for context in get_presentation_asset_containers(asset):
		if ICourseInstance.providedBy(context):
			containers = chain((context,), get_course_packages(context))
		else:
			containers = (context,)
		for container in containers:
			if 		INTICourseOverviewGroup.providedBy(container) \
				and INTILessonOverview.providedBy(container) \
				and INTIMediaRoll.providedBy(container) \
				and INTISlideDeck.providedBy(container) \
				and container.remove(asset):
				# XXX: notify the item asset container has been modified
				# when an underlying asset has been removed
				notify(ItemRemovedFromItemAssetContainerEvent(container, asset))
			else:
				mapping = IPresentationAssetContainer(container, None)
				if mapping is not None:
					mapping.pop(asset.ntiid, None)
