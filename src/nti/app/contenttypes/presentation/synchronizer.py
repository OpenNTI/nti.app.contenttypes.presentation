#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import six
import copy
import time
import simplejson
from urlparse import urlparse

from zope import component
from zope import lifecycleevent

from zope.component.hooks import getSite

from zope.interface.interfaces import IMethod

from zope.intid.interfaces import IIntIds

from ZODB.interfaces import IConnection

from nti.app.products.courseware.utils import transfer_resources_from_filer

from nti.app.contenttypes.presentation.interfaces import IItemRefValidator

from nti.app.contenttypes.presentation.utils.asset import db_connection
from nti.app.contenttypes.presentation.utils.asset import add_2_connection
from nti.app.contenttypes.presentation.utils.asset import allowed_in_registry
from nti.app.contenttypes.presentation.utils.asset import check_docket_targets
from nti.app.contenttypes.presentation.utils.asset import create_lesson_4_node
from nti.app.contenttypes.presentation.utils.asset import remove_presentation_asset

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.cabinet.filer import DirectoryFiler

from nti.contentfile.interfaces import IContentBaseFile

from nti.contentlibrary.indexed_data import get_site_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.common import get_course_packages
from nti.contenttypes.courses.common import get_course_site_registry

from nti.contenttypes.courses.interfaces import NTI_COURSE_FILE_SCHEME

from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import	CourseLessonSyncResults
from nti.contenttypes.courses.interfaces import	ICourseOutlineContentNode

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_hierarchy

from nti.contenttypes.presentation import interface_of_asset
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IItemAssetContainer
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraints
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.contenttypes.presentation.media import NTIVideoRoll

from nti.contenttypes.presentation.utils import create_ntilessonoverview_from_external

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.internalization import update_from_external_object

from nti.intid.common import addIntId
from nti.intid.common import removeIntId

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import is_ntiid_of_type
from nti.ntiids.ntiids import make_provider_safe
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.interfaces import IRecordable
from nti.recorder.interfaces import IRecordableContainer

from nti.recorder.record import copy_transaction_history
from nti.recorder.record import remove_transaction_history

from nti.publishing.interfaces import IPublishable
from nti.publishing.interfaces import ICalendarPublishable

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS

def _prepare_json_text(s):
	result = s.decode('utf-8') if isinstance(s, bytes) else s
	return result
prepare_json_text = _prepare_json_text

def _is_obj_locked(item):
	return IRecordable.providedBy(item) and item.isLocked()

def _is_child_order_locked(item):
	return IRecordableContainer.providedBy(item) and item.isChildOrderLocked()

def _can_be_removed(registered, force=False):
	result = registered is not None and (force or not _is_obj_locked(registered))
	return result
can_be_removed = _can_be_removed

def _unregister(registry, provided=None, name=None):
	result = unregisterUtility(registry, provided=provided, name=name)
	if not result and allowed_in_registry(provided):
		logger.warn("Could not unregister (%s,%s) during sync, continuing...",
					provided.__name__, name)
	else:
		logger.debug("(%s,%s) has been unregistered", provided.__name__, name)
	return result

def _intid_register(item, intids=None, connection=None):
	intids = component.queryUtility(IIntIds) if intids is None else intids
	if 		intids is not None \
		and intids.queryId(item) is None \
		and add_2_connection(item, connection=connection):
		addIntId(item)
		return True
	return False

def _intid_unregister(item, intids=None):
	intids = component.queryUtility(IIntIds) if intids is None else intids
	if intids is not None and intids.queryId(item) is not None:
		removeIntId(item)
		return True
	return False

def _removed_registered(provided, name, intids=None, registry=None,
						catalog=None, force=False):
	registry = get_site_registry(registry)
	registered = registry.queryUtility(provided, name=name)
	intids = component.getUtility(IIntIds) if intids is None else intids
	if _can_be_removed(registered, force=force):
		catalog = get_library_catalog() if catalog is None else catalog
		catalog.unindex(registered, intids=intids)
		registered.__parent__ = None  # ground
		_intid_unregister(registered, intids)
		_unregister(registry, provided=provided, name=name)
	elif registered is not None:
		logger.warn("Object (%s,%s) is locked cannot be removed during sync",
					provided.__name__, name)
		registered = None  # set to None since it was not removed
	return registered
removed_registered = _removed_registered

def _register_utility(item, provided, ntiid, registry=None):
	#if not allowed_in_registry(provided):
	#	return (False, item)
	if provided.providedBy(item):
		registry = get_site_registry(registry)
		registered = registry.queryUtility(provided, name=ntiid)
		if registered is None:
			assert is_valid_ntiid_string(ntiid), "invalid NTIID %s" % ntiid
			registerUtility(registry, item, provided=provided, name=ntiid)
			logger.info("(%s,%s) has been registered", provided.__name__, ntiid)
			return (True, item)
		return (False, registered)
	return (False, None)

# Courses

def _asset_container(context):
	container = IPresentationAssetContainer(context, None)
	return container if container is not None else dict()

def _remove_registered_course_overview(name=None, registry=None, course=None, force=False):
	result = []
	container = _asset_container(course)

	# unregister group
	group = _removed_registered(INTICourseOverviewGroup,
								name=name,
								force=force,
								registry=registry)
	if group is not None:
		result.append(group)
		container.pop(name, None)
	else:
		group = ()

	def _do_remove(obj):
		ntiid = obj.ntiid
		concrete = IConcreteAsset(obj, obj)
		if 		concrete is not obj \
			and IUserCreatedAsset.providedBy(concrete) \
			and not IContentBackedPresentationAsset.providedBy(concrete):
			_do_remove(concrete)

		removed = _removed_registered(interface_of_asset(obj),
									  name=ntiid,
								   	  registry=registry,
								  	  force=force)
		if removed is not None:
			result.append(removed)
			container.pop(ntiid, None)

		if INTIMediaRoll.providedBy(obj):
			# remove each item in our roll
			for roll_item in item:
				_do_remove(roll_item)

	# unregister child elements
	for item in group:
		if not IContentBackedPresentationAsset.providedBy(item):
			_do_remove(item)

	return result

def _remove_registered_lesson_overview(name, registry=None, course=None, force=False):
	# remove lesson overviews
	result = []
	overview = _removed_registered(INTILessonOverview,
								   name=name,
								   force=force,
								   registry=registry)
	if overview is None:
		return result
	else:  # remove from container
		container = _asset_container(course)
		container.pop(name, None)
		result.append(overview)

	# remove all groups
	for group in overview:
		result.extend(_remove_registered_course_overview(name=group.ntiid,
													 	 force=force,
										   			 	 registry=registry,
										   			 	 course=course))
	return result
remove_registered_lesson_overview = _remove_registered_lesson_overview

def _register_media_rolls(roll, registry=None, validate=False):
	idx = 0
	items = roll.Items
	registry = get_site_registry(registry)

	while idx < len(items):  # mutating
		item = items[idx]
		item_iface = interface_of_asset(item)
		result, registered = _register_utility(item,
										 	   ntiid=item.ntiid,
										  	   registry=registry,
										  	   provided=item_iface)

		validator = IItemRefValidator(item, None)
		is_valid = (not validate or validator is None or validator.validate())
		if not is_valid:  # don't include in the roll
			del items[idx]
			continue
		elif not result:  # replace if registered before
			items[idx] = registered
		idx += 1
	return roll

def _is_auto_roll_coalesce(item):
	return 		(INTIMedia.providedBy(item) or INTIMediaRef.providedBy(item)) \
			and not _is_obj_locked(item)

def _validate_ref(item, validate):
	validator = IItemRefValidator(item, None)
	return (not validate or validator is None or validator.validate())

def _do_register(item, registry):
	item_iface = interface_of_asset(item)
	return _register_utility(item,
							 ntiid=item.ntiid,
							 registry=registry,
							 provided=item_iface)

def _is_lesson_sync_locked(existing_overview):
	"""
	As an optimization, we say a lesson is sync locked if *any*
	children (recursively) of the lesson are locked. Without this
	optimization, we would have to have reproduceable NTIIDs at
	the group and asset level, so that we could appropriately merge
	and preserve transaction history. This gets difficult when
	media rolls are auto-created during sync time.
	"""
	# Currently only return first locked item for efficiency.
	locked_items = []
	def _recur(item):
		item = IConcreteAsset(item, item)
		if _is_obj_locked(item) or _is_child_order_locked(item):
			locked_items.append(item.ntiid)
			return True
		children = getattr(item, 'Items', None)
		for child in children or ():
			if _recur(child):
				return True
		return False

	result = _recur(existing_overview)
	return result, locked_items

def _add_2_course_container(course, item, catalog, node=None):
	item.__parent__ = course
	namespace = getattr(node, 'src', None)
	entry = ICourseCatalogEntry(course, None)
	ntiids = (entry.ntiid,) if entry is not None else ()
	# add in asset container
	container = _asset_container(course)
	container[item.ntiid] = item
	# index
	_intid_register(item)
	catalog.index(item,
				  sites=getSite().__name__,
			  	  namespace=namespace,
				  container_ntiids=ntiids)

def _update_sync_results(lesson_ntiid, sync_results, lesson_locked):
	field = 'LessonsSyncLocked' if lesson_locked else 'LessonsUpdated'
	if sync_results is not None:
		lessons = sync_results.Lessons
		if lessons is None:
			sync_results.Lessons = lessons = CourseLessonSyncResults()
		getattr(lessons, field).append(lesson_ntiid)

def _update_asset_state(asset, parsed, course, source_filer=None,
						target_filer=None, connection=None):
	"""
	Finalize our lesson/asset state by setting locked and publication
	state. We also transfer file docs/images into our course resources
	file store.
	"""
	asset = IConcreteAsset(asset, asset)
	modified = False
	locked = parsed.get('isLocked')
	if locked and IRecordable.providedBy(asset):
		asset.lock(event=False)
		modified = True

	locked = parsed.get('isChildOrderLocked')
	if locked and IRecordableContainer.providedBy(asset):
		asset.childOrderLock(event=False)
		modified = True

	isPublished = parsed.get('isPublished')
	if isPublished or isPublished is None:
		if ICalendarPublishable.providedBy(asset):
			if not asset.publishBeginning:
				asset.publish(event=False)
				modified = True
		elif IPublishable.providedBy(asset):
			asset.publish(event=False)
			modified = True

	ext_obj = parsed.get('PublicationConstraints')
	if ext_obj:
		# add asset to the connection since we need to get intids
		# for the constraints
		if connection is not None and IConnection(asset, None) is None:
			connection.add(asset)
		constraints = ILessonPublicationConstraints(asset)
		update_from_external_object(constraints, ext_obj, notify=False)
		modified = True

	# Now update our hrefs/icons, if necessary.
	if course is not None:
		target_filer = get_course_filer(course) if target_filer is None else target_filer
		if source_filer is None and os.path.exists( course.root.absolute_path ):
			source_filer = DirectoryFiler(course.root.absolute_path)
		if source_filer is not None:
			transfer_resources_from_filer(interface_of_asset(asset),
										  asset,
										  source_filer,
										  target_filer)

	# Update recursively
	if IItemAssetContainer.providedBy( asset ):
		# Will these always be the same length...?
		for child, parsed_child in zip( asset.Items or (),
										parsed.get( 'Items' ) or [] ):
			if parsed_child:
				_update_asset_state( child, parsed_child, course,
									 source_filer, target_filer, connection)

	if modified:
		lifecycleevent.modified(asset)

def _load_and_register_lesson_overview_json(jtext, registry=None, ntiid=None,
											validate=False, course=None,
											node=None, sync_results=None,
											intids=None, connection=None):
	registry = get_site_registry(registry)

	# read and parse json text
	catalog = get_library_catalog()
	jtext = _prepare_json_text(jtext)
	json_data = simplejson.loads(jtext)
	source_data = copy.deepcopy(json_data) # copy for tracking
	# We'll handle this on update, manually.
	json_data.pop('PublicationConstraints', None)
	overview = create_ntilessonoverview_from_external(json_data, notify=False)

	existing_overview = registry.queryUtility(INTILessonOverview, name=overview.ntiid)
	is_locked, locked_ntiids = _is_lesson_sync_locked(existing_overview)
	_update_sync_results(overview.ntiid, sync_results, is_locked)
	if is_locked:
		logger.info('Not syncing lesson (%s) (locked=%s)', overview.ntiid, locked_ntiids)
		# We may update lesson/asset state even if locked...
		_update_asset_state(existing_overview, source_data, course,
							connection=connection)
		return existing_overview, ()

	# remove and register
	removed = _remove_registered_lesson_overview(name=overview.ntiid,
									   			 registry=registry,
									   			 course=course)

	overview.__parent__ = node  # set lineage
	_register_utility(overview, INTILessonOverview, overview.ntiid, registry)

	# canonicalize group
	groups = overview.Items or ()
	json_groups = source_data.get(ITEMS)
	for gdx, group in enumerate(groups):

		# register course overview group
		did_register_new_item, registered = _register_utility(group,
											   				  INTICourseOverviewGroup,
											   				  group.ntiid,
											  				  registry)
		if not did_register_new_item:
			groups[gdx] = group = registered

		# set lineage
		registered.__parent__ = overview

		idx = 0
		items = group.Items or ()
		json_items = json_groups[gdx].get(ITEMS)

		# canonicalize item refs
		while idx < len(items):
			item = items[idx]
			# there are cases where the internalization of the
			# asset produces more than one object. (e.g. discussions
			# with multiple ntiids). If that happens, then the source
			# items do not line up with the input json.
			if _is_auto_roll_coalesce(item):
				# Ok, we have media that we want to auto-coalesce into a roll.
				roll_idx = idx
				roll_item = item
				# TODO: generalize media type
				media_roll = NTIVideoRoll()

				# coalesce into a media roll
				while _is_auto_roll_coalesce(roll_item):
					# It should be ok if this is called multiple times on object.
					_, registered = _do_register(roll_item, registry)

					# Transform any media to a media ref since media rolls
					# only contain refs
					if INTIMedia.providedBy(registered):
						# register media w/ course packges
						_intid_register(registered)
						_add_2_course_container(course, registered, catalog, node)
						# create mediaref and register it
						media_ref = INTIMediaRef(registered)
						_, registered = _do_register(media_ref, registry)

					if _validate_ref(registered, validate):
						media_roll.append(registered)

					roll_idx += 1
					roll_item = items[roll_idx] if roll_idx < len(items) else None

				# Must have at least two items in our auto-roll; otherwise continue on.
				if len(media_roll) > 1:
					logger.debug('Built video roll (%s) (%s)', overview.ntiid,
								media_roll.ntiid)
					# Should always be new.
					_do_register(media_roll, registry)
					items[idx] = media_roll
					json_items[idx] = to_external_object(media_roll, decorate=False)
					idx += 1
					# Make sure to update our index/delete contained indexes.
					del items[idx:roll_idx]
					del json_items[idx:roll_idx]
					continue
			elif INTIDiscussionRef.providedBy(item) and item.isCourseBundle() and ntiid:
				specific = get_specific(ntiid)
				provider = make_provider_safe(specific) if specific else None
				if provider:  # check for safety
					new_ntiid = make_ntiid(provider=provider, base=item.ntiid)
					item.ntiid = new_ntiid
			elif INTIMediaRoll.providedBy(item):
				_register_media_rolls(item, registry=registry, validate=validate)
			elif INTITimeline.providedBy(item) or INTIRelatedWorkRef.providedBy(item):
				ntiid = item.ntiid or u''
				found = find_object_with_ntiid(ntiid)
				if 		found is not None \
					and not IContentBackedPresentationAsset.providedBy(found):
					# Remove and register our mew object if we not content backed.
					# This could be a related work ref only present in the Lessons
					# folder of a course (import/export/synced). Therefore we must
					# update if not locked.
					removed_item = _removed_registered(interface_of_asset( found ),
													   ntiid,
													   intids,
													   registry)
					if removed_item is not None:
						found = None

				if found is None:
					# Register the new object
					assert ntiid, 'Must provide an ntiid'
					_, registered = _do_register(item, registry)
					_add_2_course_container(course, registered, catalog, node)
					found = registered

				if INTITimeline.providedBy(found):
					item = INTITimelineRef(found)  # transform to ref
				elif INTIRelatedWorkRef.providedBy(found):
					item = INTIRelatedWorkRefPointer(found) # transform to ref

				# add to items
				items[idx] = item
			# register item
			result, registered = _do_register(item, registry)
			is_valid = _validate_ref(item, validate)
			if not is_valid:  # don't include in the group
				del items[idx]
				del json_items[idx]
				continue
			elif not result:  # replace if registered before
				items[idx] = registered
			idx += 1

		# set lineage just in case for non package assets
		for item in items or ():
			# Register here before updating asset state
			_intid_register(item, intids, connection=connection)
			if not IContentBackedPresentationAsset.providedBy(item):
				item.__parent__ = group

	_update_asset_state(overview, source_data, course, connection=connection)
	return overview, removed

def _copy_remove_transactions(items, registry=None):
	registry = get_site_registry(registry)
	for item in items or ():
		provided = interface_of_asset(item)
		obj = registry.queryUtility(provided, name=item.ntiid)
		if obj is None:
			remove_transaction_history(item)
		else:
			copy_transaction_history(item, obj)

def _get_source_lastModified(source, catalog=None):
	catalog = get_library_catalog() if catalog is None else catalog
	key = '%s.lastModified' % source
	result = catalog.get_last_modified(key)
	return result

def _set_source_lastModified(source, lastModified=0, catalog=None):
	catalog = get_library_catalog() if catalog is None else catalog
	key = '%s.lastModified' % source
	catalog.set_last_modified(key, lastModified)

def _remove_source_lastModified(source, catalog=None):
	catalog = get_library_catalog() if catalog is None else catalog
	key = '%s.lastModified' % source
	catalog.remove_last_modified(key)

def _outline_nodes(outline):
	result = []
	def _recur(node):
		# We only want leaf nodes here; rather any content nodes or
		# nodes with sources.
		if getattr(node, 'src', None) or ICourseOutlineContentNode.providedBy(node):
			result.append(node)

		# parse children
		for child in node.values():
			_recur(child)

	if outline is not None:
		_recur(outline)
	return result

def _create_lesson_4_node(node, registry=None, catalog=None):
	"""
	Possibly legacy calendar, 'stub' nodes.  We want these created,
	unpublished and unlocked so that they can be updated on sync.
	"""
	result = create_lesson_4_node(node, registry=registry,
								  catalog=catalog, sites=getSite().__name__)
	return result

def _remove_and_unindex_course_assets(container_ntiids=None, namespace=None,
									  catalog=None, intids=None,
									  registry=None, course=None,
									  sites=None, force=False):

	catalog = get_library_catalog() if catalog is None else catalog
	intids = component.getUtility(IIntIds) if intids is None else intids

	result = []
	locked = set()
	sites = get_component_hierarchy_names() if not sites else sites

	# unregister and unindex lesson overview obects
	for item in catalog.search_objects(intids=intids,
									   provided=INTILessonOverview,
									   container_ntiids=container_ntiids,
									   container_all_of=False,
									   namespace=namespace,
									   sites=sites):
		# don't remove any locked lessons
		is_locked, _ = _is_lesson_sync_locked(item)
		if not is_locked:
			result.extend(_remove_registered_lesson_overview(name=item.ntiid,
										   			 	 	 registry=registry,
										   			 	 	 force=force,
										   			  	 	 course=course))
		elif not force:
			locked.add(item.ntiid)

	if container_ntiids:  # unindex all other objects
		container = _asset_container(course)
		objs = catalog.search_objects(container_ntiids=container_ntiids,
									  container_all_of=False,
									  namespace=namespace,
									  sites=sites,
									  intids=intids)
		for obj in objs or ():
			doc_id = intids.queryId(obj)
			# ignore objects that belong to locked lesson
			lesson = find_interface(obj, INTILessonOverview, strict=False)
			if lesson is not None and lesson.ntiid in locked:
				continue
			if doc_id is not None:
				catalog.remove_containers(doc_id, container_ntiids)
			if _can_be_removed(obj, force) and obj.ntiid:  # check for a valid ntiid
				container.pop(obj.ntiid, None)
	return result
remove_and_unindex_course_assets = _remove_and_unindex_course_assets

def _make_set(target):
	if target is None:
		target = set()
	elif isinstance(target, six.string_types):
		target = {target}
	elif not isinstance(target, set):
		target = set(target)
	return target

def _recurse_copy(ntiids, *items):
	ntiids = ntiids.copy() if ntiids is not None else set()
	ntiids.update(items)
	return ntiids

def _set_internal_resource_from_filer(provided, obj, filer):
	result = {}
	for field_name in provided:
		if field_name.startswith('_'):
			continue
		value = getattr(obj, field_name, None)
		if 		value is not None \
			and not IMethod.providedBy(value) \
			and isinstance(value, six.string_types) \
			and value.startswith(NTI_COURSE_FILE_SCHEME):

			path = urlparse(value).path
			bucket, name = os.path.split(path)
			bucket = None if not bucket else bucket

			if filer.contains(key=name, bucket=bucket):
				item = filer.get(key=name, bucket=bucket)
				href = filer.get_external_link(item)
				if IContentBaseFile.providedBy(item):
					item.add_association(obj)
					lifecycleevent.modified(item)
				setattr(obj, field_name, href)
				result[field_name] = href

	check_docket_targets(obj)
	return result

def _index_overview_items(items, container_ntiids=None, namespace=None,
						  intids=None, catalog=None, node=None, course=None,
						  parent=None, connection=None):
	# make it a set
	container_ntiids = _make_set(container_ntiids)

	filer = get_course_filer(course)
	container = _asset_container(course)
	sites = get_component_hierarchy_names()
	catalog = get_library_catalog() if catalog is None else catalog

	if parent is not None:
		to_index = _recurse_copy(container_ntiids, parent.ntiid)
	else:
		to_index = container_ntiids

	for item in items or ():

		# XXX: In alpha some items don't have a valid ntiid
		if not item.ntiid:
			continue

		container[item.ntiid] = item

		# set lesson overview NTIID on the outline node
		if INTILessonOverview.providedBy(item) and node is not None:
			item.__parent__ = node  # lineage
			node.LessonOverviewNTIID = item.ntiid
			# XXX If there is no lesson set it to the overview
			if hasattr(node, 'ContentNTIID') and not node.ContentNTIID:
				node.ContentNTIID = item.ntiid

		if IItemAssetContainer.providedBy(item):

			_index_overview_items(item.Items,
								  namespace=namespace,
								  container_ntiids=to_index,
								  intids=intids,
								  catalog=catalog,
								  node=node,
								  course=course,
								  parent=item)

			# register and index
			_intid_register(item, intids, connection=connection)
			catalog.index(item,
						  sites=sites,
						  intids=intids,
						  namespace=namespace,
						  container_ntiids=to_index)
		else:
			ns_name = None if IPackagePresentationAsset.providedBy(item) else namespace
			_intid_register(item, intids, connection=connection)
			catalog.index(item,
						  sites=sites,
						  intids=intids,
						  namespace=ns_name,
						  container_ntiids=to_index)
			concrete = IConcreteAsset(item, item)
			if concrete is not item:
				catalog.index(concrete,
						 	  intids=intids,
						 	  container_ntiids=to_index)

		# set any internal resource after gaining an intid
		provided = interface_of_asset(item)
		if filer is not None:
			_set_internal_resource_from_filer(provided, item, filer)

def _index_pacakge_assets(course, catalog=None, sites=None):
	entry = ICourseCatalogEntry(course)
	packs = get_course_packages(course)
	packs = tuple(x.ntiid for x in packs)

	catalog = get_library_catalog() if catalog is None else catalog
	sites = get_component_hierarchy_names() if not sites else sites

	for doc_id in catalog.get_references(provided=PACKAGE_CONTAINER_INTERFACES,
									   	 container_ntiids=packs,
									   	 container_all_of=False,
									   	 sites=sites):
		catalog.update_containers(doc_id, (entry.ntiid,))
index_pacakge_assets = _index_pacakge_assets

def get_cataloged_namespaces(ntiid, catalog=None, sites=None):
	catalog = get_library_catalog() if catalog is None else catalog
	sites = get_component_hierarchy_names() if not sites else sites
	references = catalog.get_references(provided=INTILessonOverview,
										container_ntiids=ntiid,
										sites=sites)
	index = catalog.namespace_index
	result = {v for _, v in index.zip(references)}
	result.discard(None)
	return result

def get_sibling_entry(source, unit=None, buckets=None):
	# seek in buckets first
	for bucket in buckets or ():
		result = bucket.getChildNamed(source) if bucket is not None else None
		if result is not None:
			return result
	if unit is not None:
		return unit.does_sibling_entry_exist(source)  # returns a key
	return None

def _add_buckets(course, buckets):
	root = course.root
	if root is not None:
		lessons = root.getChildNamed('Lessons')
		if lessons is not None:
			buckets.append(lessons)
		buckets.append(root)
	return buckets

def synchronize_course_lesson_overview(course, intids=None, catalog=None,
									   buckets=None, **kwargs):
	"""
	Synchronize course lesson overviews

	:param course: Course to sync
	:param intids: IntID facility
	:param catalog: Presentation assets catalog index
	:param buckets: Array of source buckets where lesson files are located
	"""
	result = []
	namespaces = set()
	parent = get_parent_course(course)
	if not buckets:  # XXX seek in Lesson directories
		buckets = list()
		if ICourseSubInstance.providedBy(course):
			_add_buckets(parent, buckets)
		_add_buckets(course, buckets)

	# capture all hierarchy entry ntiids
	hierarchy = [ICourseCatalogEntry(x).ntiid for x in get_course_hierarchy(course)]

	course_packages = get_course_packages(course)
	catalog = get_library_catalog() if catalog is None else catalog
	intids = component.getUtility(IIntIds) if intids is None else intids

	registry = get_site_registry()
	connection = db_connection(registry)
	entry = ICourseCatalogEntry(course, None)
	ntiid = entry.ntiid if entry is not None else course.__name__
	name = entry.ProviderUniqueID if entry is not None else course.__name__

	parent = ICourseCatalogEntry(parent, None)
	ref_ntiid = parent.ntiid if parent is not None else ntiid

	now = time.time()
	site = getSite().__name__
	logger.info('Synchronizing lessons overviews for %s, under site %s', name, site)

	# parse and register
	removed = []
	nodes = _outline_nodes(course.Outline)
	for node in nodes:
		# This is an import case; if the node already has a registered lesson that is
		# locked, make sure we do not re-sync (since the underlying json may not yet
		# have ntiids for us to check state up ahead). This also works because
		# we do not allow sync-updates on lesson children if the lesson (or any of its
		# children) are locked.
		lesson = INTILessonOverview(node, None)
		if lesson is not None and _is_obj_locked( lesson ):
			logger.info('Not syncing lesson for node because lesson is locked (node=%s) (lesson=%s)',
						lesson.ntiid, node.ntiid)
			continue

		# process node
		namespace = node.src
		if not namespace:
			# These are possibly the legacy calendar nodes. Stub the lesson out.
			_create_lesson_4_node(node, registry, catalog)
			continue
		elif is_ntiid_of_type(namespace, TYPE_OID):  # ignore
			continue
		# ready to sync
		namespaces.add(namespace)  # this is ntiid based file (unique)
		for content_package in course_packages:
			sibling_key = get_sibling_entry(namespace, content_package, buckets)
			if not sibling_key:
				break

			sibling_lastModified = sibling_key.lastModified
			root_lastModified = _get_source_lastModified(namespace, catalog)
			if root_lastModified >= sibling_lastModified:
				# we want to associate the ntiid of the new course with the
				# assets and set the lesson overview ntiid to the outline node
				objects = catalog.search_objects(namespace=namespace,
												 provided=INTILessonOverview,
												 container_ntiids=hierarchy,
												 container_all_of=False,
												 intids=intids)
				_index_overview_items(objects,
									  namespace=namespace,
									  container_ntiids=ntiid,
									  catalog=catalog,
									  intids=intids,
									  node=node,
									  course=course,
									  connection=connection)

				continue

			# this remove all lesson overviews and overview groups
			# for specified namespace file. As of 20150521 we
			# don't allow sharing of lesson amongst different courses
			# (not in hierarchy)...and overview groups are unique to
			# its own lesson
			removed.extend(_remove_and_unindex_course_assets(namespace=namespace,
															 container_ntiids=ntiid,
															 registry=registry,
															 catalog=catalog,
															 intids=intids,
															 course=course))

			logger.info("Synchronizing %s", namespace)

			index_text = sibling_key.readContents()
			overview, rmv = _load_and_register_lesson_overview_json(
											index_text,
											node=node,
											validate=True,
											course=course,
											ntiid=ref_ntiid,
											registry=registry,
											intids=intids,
											connection=connection,
											**kwargs)
			removed.extend(rmv)
			result.append(overview)

			# index
			_index_overview_items((overview,),
								  namespace=namespace,
								  container_ntiids=ntiid,
								  catalog=catalog,
								  intids=intids,
								  node=node,
								  course=course,
								  connection=connection)

			# publish by default if not locked
			if not _is_lesson_sync_locked(overview)[0]:  # returns an array
				overview.publish(event=False)

			_set_source_lastModified(namespace, sibling_lastModified, catalog)

	# finally copy transactions from removed to new objects
	_copy_remove_transactions(removed, registry=registry)

	_index_pacakge_assets(course, catalog=catalog)

	logger.info('Lessons overviews for %s have been synchronized in %s(s)',
				 name, time.time() - now)

	return result

def _clear_course_assets(course, unregister=True):
	container = _asset_container(course)
	if unregister:
		catalog = get_library_catalog()
		registry = get_course_site_registry(course)

		# remove user created concrete assets
		for ntiid, item in list(container.items()): # modifying
			concrete = IConcreteAsset(item, None)
			if 		IUserCreatedAsset.providedBy(concrete) \
				and not IContentBackedPresentationAsset.providedBy(concrete):
				remove_presentation_asset(concrete, registry, catalog, name=ntiid)

		# remove the rest
		for ntiid, item in list(container.items()): # modifying
			remove_presentation_asset(item, registry, catalog, name=ntiid)

	# clear all
	container.clear()
clear_course_assets = _clear_course_assets

def _clear_namespace_last_modified(course, catalog=None):
	nodes = _outline_nodes(course.Outline)
	for node in nodes or ():
		namespace = node.src or u''  # this is ntiid based file (unique)
		_remove_source_lastModified(namespace, catalog)
clear_namespace_last_modified = _clear_namespace_last_modified
