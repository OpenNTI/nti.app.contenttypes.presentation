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
from itertools import chain

from zope.intid import IIntIds

from zope import component

from zope.interface.interfaces import IUnregistered

from zope.lifecycleevent import IObjectRemovedEvent

from ZODB.interfaces import IConnection

from nti.coremetadata.interfaces import IRecordable

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import	ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceAvailableEvent

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import IWillRemovePresentationAssetEvent

from nti.contenttypes.presentation.utils import create_lessonoverview_from_external

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import make_ntiid, find_object_with_ntiid
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_provider_safe
from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.recorder.record import copy_transaction_history
from nti.recorder.record import remove_transaction_history

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility
from nti.site.site import get_component_hierarchy_names

from nti.wref.interfaces import IWeakRef

from .interfaces import IItemRefValidator

from .utils import get_course_packages
from .utils import get_presentation_asset_containers

from . import iface_of_thing

ITEMS = StandardExternalFields.ITEMS

def prepare_json_text(s):
	result = unicode(s, 'utf-8') if isinstance(s, bytes) else s
	return result

def _can_be_removed(registered, force=False):
	result = registered is not None and \
			 (force or not IRecordable.providedBy(registered) or not registered.locked)
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
		if not unregisterUtility(registry, component=registered,
								 provided=provided, name=name):
			logger.warn("Could not unregister (%s,%s) during sync, continuing...",
						provided.__name__, name)
		intids.unregister(registered, event=False)
	elif registered is not None:
		logger.warn("Object (%s,%s) is locked cannot be removed during sync",
					provided.__name__, name)
		registered = None  # set to None since it was not removed
	return registered

def _db_connection(registry=None):
	registry = get_registry(registry)
	if registry == component.getGlobalSiteManager():
		result = None
	else:
		result = IConnection(registry, None)
	return result

def intid_register(item, registry, intids=None, connection=None):
	intids = component.getUtility(IIntIds) if intids is None else intids
	connection = _db_connection(registry) if connection is None else connection
	if connection is not None:
		connection.add(item)
		intids.register(item, event=False)
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
			intid_register(item, registry, intids, connection)
			return (True, item)
		return (False, registered)
	return (False, None)

# Courses

from . import PACKAGE_CONTAINER_INTERFACES

def _remove_registered_course_overview(name=None, registry=None,
									   course=None, force=False):
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

	# For each group remove anything that is not synced in the content pacakge.
	# As of 20150404 we don't have a way to edit and register common group
	# overview items so we need to remove the old and re-register the new
	for item in group:  # this shoud resolve weak refs
		iface = iface_of_thing(item)
		if iface not in PACKAGE_CONTAINER_INTERFACES:
			ntiid = item.ntiid
			removed = _removed_registered(iface,
										  name=ntiid,
								   		  registry=registry,
								  		  force=force)
			if removed is not None:
				result.append(removed)
				container.pop(item.ntiid, None)
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

def _load_and_register_lesson_overview_json(jtext, registry=None, ntiid=None,
											validate=False, course=None):
	registry = get_registry(registry)

	# read and parse json text
	data = simplejson.loads(prepare_json_text(jtext))
	overview = create_lessonoverview_from_external(data, notify=False)

	# remove and register
	removed = _remove_registered_lesson_overview(name=overview.ntiid,
									   			 registry=registry,
									   			 course=course)

	_register_utility(overview, INTILessonOverview, overview.ntiid, registry)

	# canonicalize group
	groups = overview.Items
	for gdx, group in enumerate(groups):
		# register course overview roup
		result, registered = _register_utility(group,
											   INTICourseOverviewGroup,
											   group.ntiid,
											   registry)
		if not result:  # replace if registered before
			groups[gdx] = registered

		# set lineage
		registered.__parent__ = overview

		idx = 0
		items = group.Items

		# canonicalize item refs
		while idx < len(items):
			item = items[idx]
			# check for weak refs in case has been canonicalized
			item = item() if IWeakRef.providedBy(item) else item
			if item is None:
				del items[idx]
				continue

			if INTIDiscussionRef.providedBy(item) and item.isCourseBundle() and ntiid:
				specific = get_specific(ntiid)
				provider = make_provider_safe(specific) if specific else None
				if provider:  # check for safety
					new_ntiid = make_ntiid(provider=provider, base=item.ntiid)
					item.ntiid = new_ntiid

			item_iface = iface_of_thing(item)
			result, registered = _register_utility(item,
											 	   ntiid=item.ntiid,
											  	   registry=registry,
											  	   provided=item_iface)

			validator = IItemRefValidator(item, None)
			is_valid = (not validate or validator is None or \
						validator.validate())

			if not is_valid:  # don't include in the ovewview
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

def get_course_packages(context):
	packages = ()
	context = ICourseInstance(context)
	try:
		packages = context.ContentPackageBundle.ContentPackages
	except AttributeError:
		packages = (context.legacy_content_package,)
	return packages

def _outline_nodes(outline):
	result = []
	def _recur(node):
		src = getattr(node, 'src', None)
		if src:
			result.append(node)

		# parse children
		for child in node.values():
			_recur(child)

	if outline is not None:
		_recur(outline)
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

	for item in items:
		item = item() if IWeakRef.providedBy(item) else item
		if item is None:
			continue

		item.publish()  # by default

		if container is not None:
			container[item.ntiid] = item

		# set lesson overview NTIID on the outline node
		if INTILessonOverview.providedBy(item) and node is not None:
			item.__parent__ = node  # lineage
			node.LessonOverviewNTIID = item.ntiid

		# for lesson and groups overviews index all fields
		if 	INTILessonOverview.providedBy(item) or \
			INTICourseOverviewGroup.providedBy(item):

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
			# because and item can be in different groups with different
			# namespace
			catalog.index(item,
						  sites=sites,
						  intids=intids,
						  container_ntiids=to_index)

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

def synchronize_course_lesson_overview(course, intids=None, catalog=None):
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
	cataloged = get_cataloged_namespaces(ntiid, catalog)
	logger.info('Synchronizing lessons overviews for %s', name)

	# parse and register
	removed = []
	nodes = _outline_nodes(course.Outline)
	for node in nodes:
		namespace = node.src  # this is ntiid based file (unique)
		namespaces.add(namespace)
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
																	registry=registry)
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

			_set_source_lastModified(namespace, sibling_lastModified, catalog)

	# remove any lesson overview items that were dropped
	difference = cataloged.difference(namespaces)
	if difference:
		_remove_and_unindex_course_assets(namespace=difference,
										  container_ntiids=ntiid,
										  registry=registry,
										  catalog=catalog,
										  intids=intids,
										  course=course)

	# finally copy transactions from removed to new objects
	_copy_remove_transactions(removed, registry=registry)

	logger.info('Lessons overviews for %s have been synchronized in %s(s)',
				 name, time.time() - now)
	return result

@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _on_course_instance_available(course, event):
	catalog = get_library_catalog()
	if catalog is not None and not ILegacyCourseInstance.providedBy(course):
		synchronize_course_lesson_overview(course, catalog=catalog)

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

@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _clear_data_when_course_removed(course, event):
	catalog = get_library_catalog()
	if catalog is None or ILegacyCourseInstance.providedBy(course):
		return

	# clear containers
	_clear_course_assets(course)
	_clear_namespace_last_modified(course, catalog)

	# unregister assets
	entry = ICourseCatalogEntry(course, None)
	ntiid = entry.ntiid if entry is not None else course.__name__
	removed = _remove_and_unindex_course_assets(container_ntiids=ntiid,
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

@component.adapter(IPresentationAsset, IWillRemovePresentationAssetEvent)
def _on_will_remove_presentation_asset(asset, event):
	ntiid = getattr(asset, 'ntiid', None)
	if not ntiid:
		return
	# remove from containers
	for context in get_presentation_asset_containers(asset):
		if ICourseInstance.providedBy(context):
			containers = chain((context,), get_course_packages(context))
		else:
			containers = (context,)
		for container in containers:
			mapping = IPresentationAssetContainer(container, None)
			if mapping is not None:
				mapping.pop(asset.ntiid, None)
