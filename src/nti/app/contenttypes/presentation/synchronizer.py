#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import time
import simplejson

from zope import component

from zope.intid.interfaces import IIntIds

from nti.coremetadata.interfaces import IRecordable
from nti.coremetadata.interfaces import IPublishable

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_packages

from nti.contenttypes.courses.interfaces import	ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import	CourseLessonSyncResults
from nti.contenttypes.courses.interfaces import	ICourseOutlineContentNode

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.media import NTIVideoRoll
from nti.contenttypes.presentation.media import media_to_mediaref

from nti.contenttypes.presentation.utils import create_lessonoverview_from_external

from nti.externalization.interfaces import StandardExternalFields

from nti.intid.common import addIntId
from nti.intid.common import removeIntId

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import is_ntiid_of_type
from nti.ntiids.ntiids import make_provider_safe
from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.recorder.record import copy_transaction_history
from nti.recorder.record import remove_transaction_history

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility
from nti.site.site import get_component_hierarchy_names

from .interfaces import IItemRefValidator

from .utils import add_2_connection
from .utils import create_lesson_4_node

from . import iface_of_thing

from . import PACKAGE_CONTAINER_INTERFACES

ITEMS = StandardExternalFields.ITEMS

def prepare_json_text(s):
	result = unicode(s, 'utf-8') if isinstance(s, bytes) else s
	return result

def _is_obj_locked(node):
	return IRecordable.providedBy(node) and node.locked

def _can_be_removed(registered, force=False):
	result = 	registered is not None \
			and (force or not _is_obj_locked(registered))
	return result
can_be_removed = _can_be_removed

def _removed_registered(provided, name, intids=None, registry=None,
						catalog=None, force=False):
	registry = get_registry(registry)
	registered = registry.queryUtility(provided, name=name)
	intids = component.getUtility(IIntIds) if intids is None else intids
	if _can_be_removed(registered, force=force):
		catalog = get_library_catalog() if catalog is None else catalog
		catalog.unindex(registered, intids=intids)
		if not unregisterUtility(registry, provided=provided, name=name):
			logger.warn("Could not unregister (%s,%s) during sync, continuing...",
						provided.__name__, name)
		removeIntId(registered)
	elif registered is not None:
		logger.warn("Object (%s,%s) is locked cannot be removed during sync",
					provided.__name__, name)
		registered = None  # set to None since it was not removed
	return registered

def intid_register(item, registry, connection=None):
	if add_2_connection(item, registry, connection):
		addIntId(item)
		return True
	return False

def _register_utility(item, provided, ntiid, registry=None, intids=None, connection=None):
	intids = component.getUtility(IIntIds) if intids is None else intids
	if provided.providedBy(item):
		registry = get_registry(registry)
		registered = registry.queryUtility(provided, name=ntiid)
		if registered is None or intids.queryId(registered) is None:
			assert is_valid_ntiid_string(ntiid), "invalid NTIID %s" % ntiid
			if intids.queryId(registered) is None:  # remove if invalid
				unregisterUtility(registry, provided=provided, name=ntiid)
			registerUtility(registry, item, provided=provided, name=ntiid)
			intid_register(item, registry, connection=connection)
			return (True, item)
		return (False, registered)
	return (False, None)

# Courses

def _remove_registered_course_overview(name=None, registry=None, course=None, force=False):
	result = []
	container = IPresentationAssetContainer(course, None) or {}
	group = _removed_registered(INTICourseOverviewGroup,
								name=name,
								force=force,
								registry=registry)
	if group is not None:
		result.append(group)
		container.pop(name, None)
	else:
		group = ()

	def _do_remove(iface, obj):
		ntiid = obj.ntiid
		removed = _removed_registered(iface,
									  name=ntiid,
								   	  registry=registry,
								  	  force=force)
		if removed is not None:
			result.append(removed)
			container.pop(ntiid, None)

	# For each group remove anything that is not synced in the content package.
	# As of 20150404 we don't have a way to edit and register common group
	# overview items so we need to remove the old and re-register the new
	for item in group:  # this should resolve weak refs
		iface = iface_of_thing(item)
		if iface not in PACKAGE_CONTAINER_INTERFACES:
			_do_remove(iface, item)
			if INTIMediaRoll.providedBy(item):
				# Remove each item in our roll
				for roll_item in item:
					iface = iface_of_thing(roll_item)
					_do_remove(iface, roll_item)
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
		container = IPresentationAssetContainer(course, None) or {}
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
	registry = get_registry(registry)

	while idx < len(items):
		item = items[idx]
		item_iface = iface_of_thing(item)
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
	return (INTIMedia.providedBy(item)
			or 	INTIMediaRef.providedBy(item)) \
		and not _is_obj_locked(item)

def _validate_ref(item, validate):
	validator = IItemRefValidator(item, None)
	return (not validate or validator is None or validator.validate())

def _do_register(item, registry):
	item_iface = iface_of_thing(item)
	return  _register_utility(item,
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
		if _is_obj_locked(item):
			locked_items.append(item.ntiid)
			return True
		children = getattr(item, 'Items', None) or ()
		for child in children:
			if _recur(child):
				return True
		return False

	result = _recur(existing_overview)
	return result, locked_items

def _add_2_package_containers(course, catalog, item):
	ntiids = []
	packages = get_course_packages(course)
	for package in packages or ():
		ntiids.append(package.ntiid)
		container = IPresentationAssetContainer(package)
		container[item.ntiid] = item
	if ntiids:
		catalog.index(item, container_ntiids=ntiids,
				  	  namespace=ntiids[0])  # pick first

def _update_sync_results(lesson_ntiid, sync_results, lesson_locked):
	field = 'LessonsSyncLocked' if lesson_locked else 'LessonsUpdated'
	if sync_results is not None:
		lessons = sync_results.Lessons
		if lessons is None:
			sync_results.Lessons = lessons = CourseLessonSyncResults()
		getattr(lessons, field).append(lesson_ntiid)

def _load_and_register_lesson_overview_json(jtext, registry=None, ntiid=None,
											validate=False, course=None, sync_results=None):
	registry = get_registry(registry)

	# read and parse json text
	catalog = get_library_catalog()
	data = simplejson.loads(prepare_json_text(jtext))
	overview = create_lessonoverview_from_external(data, notify=False)

	existing_overview = registry.queryUtility(INTILessonOverview, name=overview.ntiid)
	is_locked, locked_ntiids = _is_lesson_sync_locked(existing_overview)
	_update_sync_results(overview.ntiid, sync_results, is_locked)
	if is_locked:
		logger.info('Not syncing lesson (%s) (locked=%s)', overview.ntiid, locked_ntiids)
		return existing_overview, ()

	# remove and register
	removed = _remove_registered_lesson_overview(name=overview.ntiid,
									   			 registry=registry,
									   			 course=course)

	_register_utility(overview, INTILessonOverview, overview.ntiid, registry)

	# canonicalize group
	groups = overview.Items or ()
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

		# canonicalize item refs
		while idx < len(items):
			item = items[idx]

			if _is_auto_roll_coalesce(item):
				# Ok, we have media that we want to auto-coalesce into a roll.
				roll_idx = idx
				roll_item = item
				# TODO: generalize media type
				media_roll = NTIVideoRoll()

				while _is_auto_roll_coalesce(roll_item):

					# It should be ok if this is called multiple times on object.
					_, registered = _do_register(roll_item, registry)

					# Transform any media to a media ref since media rolls
					# only contain refs
					if INTIMedia.providedBy(registered):
						# register media w/ course packges
						_add_2_package_containers(course, catalog, registered)
						# create mediaref and register it
						media_ref = media_to_mediaref(registered)
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
					idx += 1
					# Make sure to update our index/delete contained indexes.
					del items[idx:roll_idx]
					continue
			elif INTIDiscussionRef.providedBy(item) and item.isCourseBundle() and ntiid:
				specific = get_specific(ntiid)
				provider = make_provider_safe(specific) if specific else None
				if provider:  # check for safety
					new_ntiid = make_ntiid(provider=provider, base=item.ntiid)
					item.ntiid = new_ntiid
			elif INTIMediaRoll.providedBy(item):
				_register_media_rolls(item, registry=registry, validate=validate)

			result, registered = _do_register(item, registry)
			is_valid = _validate_ref(item, validate)
			if not is_valid:  # don't include in the group
				del items[idx]
				continue
			elif not result:  # replace if registered before
				items[idx] = registered
			idx += 1

	return overview, removed

def _copy_remove_transactions(items, registry=None):
	registry = get_registry(registry)
	for item in items or ():
		provided = iface_of_thing(item)
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
		if 		getattr(node, 'src', None) \
			or 	ICourseOutlineContentNode.providedBy(node):
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
	result = create_lesson_4_node(node, registry=registry, catalog=catalog)
	return result

def _remove_and_unindex_course_assets(container_ntiids=None, namespace=None,
									  catalog=None, intids=None,
									  registry=None, course=None,
									  sites=None, force=False):

	catalog = get_library_catalog() if catalog is None else catalog
	intids = component.getUtility(IIntIds) if intids is None else intids

	result = []
	sites = get_component_hierarchy_names() if not sites else sites
	# unregister and unindex lesson overview obects
	for item in catalog.search_objects(intids=intids, provided=INTILessonOverview,
									   container_ntiids=container_ntiids,
									   namespace=namespace,
									   sites=sites):
		result.extend(_remove_registered_lesson_overview(name=item.ntiid,
										   			 	 registry=registry,
										   			 	 force=force,
										   			  	 course=course))

	if container_ntiids:  # unindex all other objects
		container = IPresentationAssetContainer(course, None) or {}
		objs = catalog.search_objects(container_ntiids=container_ntiids,
									  namespace=namespace, sites=sites, intids=intids)
		for obj in list(objs):  # we are mutating
			doc_id = intids.queryId(obj)
			if doc_id is not None:
				catalog.remove_containers(doc_id, container_ntiids)
			if _can_be_removed(obj, force):
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

def _index_overview_items(items, container_ntiids=None, namespace=None,
						  intids=None, catalog=None, node=None, course=None,
						  parent=None):
	# make it a set
	container_ntiids = _make_set(container_ntiids)

	sites = get_component_hierarchy_names()
	catalog = get_library_catalog() if catalog is None else catalog
	container = IPresentationAssetContainer(course, None)

	if parent is not None:
		to_index = _recurse_copy(container_ntiids, parent.ntiid)
	else:
		to_index = container_ntiids

	for item in items or ():

		if container is not None:
			container[item.ntiid] = item

		# set lesson overview NTIID on the outline node
		if INTILessonOverview.providedBy(item) and node is not None:
			item.__parent__ = node  # lineage
			node.LessonOverviewNTIID = item.ntiid

		if 	INTILessonOverview.providedBy(item) or \
			INTICourseOverviewGroup.providedBy(item) or \
			INTIMediaRoll.providedBy(item):

			# for lesson and groups overviews index all fields
			namespace = None if INTIMediaRoll.providedBy(item) else namespace

			catalog.index(item,
						  sites=sites,
						  intids=intids,
						  namespace=namespace,
						  container_ntiids=to_index)

			_index_overview_items(item.Items,
								  namespace=namespace,
								  container_ntiids=to_index,
								  intids=intids,
								  catalog=catalog,
								  node=node,
								  course=course,
								  parent=item)
		else:
			# CS: We don't index items in groups with the namespace
			# because and item can be in different groups with different namespace
			catalog.index(item,
						  sites=sites,
						  intids=intids,
						  container_ntiids=to_index)

def _index_pacakge_assets(course, catalog=None, sites=None):
	entry = ICourseCatalogEntry(course)
	packs = get_course_packages(course)
	packs = [x.ntiid for x in packs]

	catalog = get_library_catalog() if catalog is None else catalog
	sites = get_component_hierarchy_names() if not sites else sites

	for doc_id in catalog.get_references(provided=PACKAGE_CONTAINER_INTERFACES,
									   	 container_ntiids=packs,
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

def synchronize_course_lesson_overview(course, intids=None, catalog=None, **kwargs):
	result = []
	namespaces = set()
	course_packages = get_course_packages(course)
	catalog = get_library_catalog() if catalog is None else catalog
	intids = component.getUtility(IIntIds) if intids is None else intids

	registry = get_registry()
	entry = ICourseCatalogEntry(course, None)
	ntiid = entry.ntiid if entry is not None else course.__name__
	name = entry.ProviderUniqueID if entry is not None else course.__name__

	parent = get_parent_course(course)
	parent = ICourseCatalogEntry(parent, None)
	ref_ntiid = parent.ntiid if parent is not None else ntiid

	now = time.time()
	logger.info('Synchronizing lessons overviews for %s', name)

	# parse and register
	removed = []
	nodes = _outline_nodes(course.Outline)
	for node in nodes:
		namespace = node.src
		if not namespace:
			# These are possibly the legacy calendar nodes. Stub
			# the lesson out.
			_create_lesson_4_node(node, registry, catalog)
			continue
		elif is_ntiid_of_type(namespace, TYPE_OID):  # ignore
			continue
		elif IRecordable.providedBy(node) and node.locked:  # ignore locked
			continue
		# ready to sync
		namespaces.add(namespace)  # this is ntiid based file (unique)
		for content_package in course_packages:
			sibling_key = content_package.does_sibling_entry_exist(namespace)
			if not sibling_key:
				break

			sibling_lastModified = sibling_key.lastModified
			root_lastModified = _get_source_lastModified(namespace, catalog)
			if root_lastModified >= sibling_lastModified:
				# we want to associate the ntiid of the new course with the
				# assets and set the lesson overview ntiid to the outline node
				objects = catalog.search_objects(namespace=namespace,
												 provided=INTILessonOverview,
												 intids=intids)
				_index_overview_items(objects,
									  namespace=namespace,
									  container_ntiids=ntiid,
									  catalog=catalog,
									  intids=intids,
									  node=node,
									  course=course)

				continue

			# this remove all lesson overviews and overview groups
			# for specified namespace file. As of 20150521 we
			# don't allow shaing of lesson amogst different courses
			# (not in hierarchy).. and overview groups are unique to
			# its own lesson
			removed.extend(_remove_and_unindex_course_assets(namespace=namespace,
															 container_ntiids=ntiid,
															 registry=registry,
															 catalog=catalog,
															 intids=intids,
															 course=course))

			logger.debug("Synchronizing %s", namespace)
			index_text = content_package.read_contents_of_sibling_entry(namespace)
			overview, rmv = _load_and_register_lesson_overview_json(index_text,
																	validate=True,
																	course=course,
																	ntiid=ref_ntiid,
																	registry=registry,
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
								  course=course)

			if IPublishable.providedBy(overview):
				overview.publish()  # by default

			_set_source_lastModified(namespace, sibling_lastModified, catalog)


	# finally copy transactions from removed to new objects
	_copy_remove_transactions(removed, registry=registry)

	_index_pacakge_assets(course, catalog=catalog)

	logger.info('Lessons overviews for %s have been synchronized in %s(s)',
				 name, time.time() - now)
	return result

def _clear_course_assets(course):
	container = IPresentationAssetContainer(course, None)
	if container is not None:
		container.clear()
clear_course_assets = _clear_course_assets

def _clear_namespace_last_modified(course, catalog=None):
	nodes = _outline_nodes(course.Outline)
	for node in nodes or ():
		namespace = node.src  # this is ntiid based file (unique)
		_remove_source_lastModified(namespace, catalog)
clear_namespace_last_modified = _clear_namespace_last_modified
