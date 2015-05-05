#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time
import simplejson

from zope.intid import IIntIds

from zope import component
from zope import lifecycleevent

from zope.lifecycleevent import IObjectRemovedEvent

from ZODB.interfaces import IConnection

from nti.app.products.courseware.interfaces import ILegacyCommunityBasedCourseInstance

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IGlobalContentPackageLibrary

from nti.contentlibrary.indexed_data.interfaces import TAG_NAMESPACE_FILE
from nti.contentlibrary.indexed_data.interfaces import IAudioIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IVideoIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import ITimelineIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import ISlideDeckIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IRelatedContentIndexedDataContainer

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import	ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceAvailableEvent

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.contenttypes.presentation.utils import create_object_from_external
from nti.contenttypes.presentation.utils import create_ntiaudio_from_external
from nti.contenttypes.presentation.utils import create_ntivideo_from_external
from nti.contenttypes.presentation.utils import create_timelime_from_external
from nti.contenttypes.presentation.utils import create_relatedwork_from_external
from nti.contenttypes.presentation.utils import create_lessonoverview_from_external

from nti.externalization.interfaces import StandardExternalFields

from nti.site.interfaces import IHostPolicySiteManager

from nti.wref.interfaces import IWeakRef

from .interfaces import IItemRefValidator

from . import get_catalog
from . import iface_of_thing

ITEMS = StandardExternalFields.ITEMS

INTERFACE_TUPLES = (
	(IAudioIndexedDataContainer, INTIAudio, create_ntiaudio_from_external),
	(IVideoIndexedDataContainer, INTIVideo, create_ntivideo_from_external), 
	(ITimelineIndexedDataContainer, INTITimeline, create_timelime_from_external),
	(ISlideDeckIndexedDataContainer, INTISlideDeck, create_object_from_external),
	(IRelatedContentIndexedDataContainer, INTIRelatedWorkRef, create_relatedwork_from_external) )

PACKAGE_CONTAINER_INTERFACES = tuple(t[1] for t in INTERFACE_TUPLES)

def prepare_json_text(s):
	result = unicode(s, 'utf-8') if isinstance(s, bytes) else s
	return result

def _registry(registry=None):
	if registry is None:
		library = component.queryUtility(IContentPackageLibrary)
		if IGlobalContentPackageLibrary.providedBy(library):
			registry = component.getGlobalSiteManager()
		else:
			registry = component.getSiteManager()
	return registry

def unregisterUtility(registry, provided, name):
	if IHostPolicySiteManager.providedBy(registry):
		return registry.subscribedUnregisterUtility(provided=provided, name=name)
	else:
		return registry.unregisterUtility(provided=provided, name=name)

def _removed_registered(provided, name, intids=None, registry=None, catalog=None):
	registry = _registry(registry)
	registered = registry.queryUtility(provided, name=name)
	if registered is not None:
		catalog = get_catalog() if catalog is None else catalog
		catalog.unindex(registered, intids=intids)
		unregisterUtility(registry, provided=provided, name=name)
		lifecycleevent.removed(registered) # remove from intids
	return registered

def _remove_from_registry(containers=None, namespace=None, provided=None, 
						  registry=None, intids=None, catalog=None):
	result = []
	registry = _registry(registry)
	catalog = get_catalog() if catalog is None else catalog
	intids = component.queryUtility(IIntIds) if intids is None else intids
	for utility in catalog.search_objects(intids=intids, provided=provided, 
										  containers=containers, namespace=namespace):
		try:
			ntiid = utility.ntiid
			if ntiid:
				result.append(utility)
				_removed_registered(provided, 
									name=ntiid, 
									intids=intids,
									catalog=catalog,
									registry=registry)
		except AttributeError:
			pass
	return result

def _connection(registry=None):
	registry = _registry(registry)
	result = IConnection(registry, None)
	return result
	
def registerUtility(registry, component, provided, name):
	if IHostPolicySiteManager.providedBy(registry):
		return registry.subscribedRegisterUtility(component,
									 			  provided=provided,
									 			  name=name)
	else:
		return registry.registerUtility(component,
									 	provided=provided,
									 	name=name)
	
def notify_object_added(item, registry, connection=None):
	connection = _connection(registry) if connection is None else connection
	if connection is not None:
		connection.add(item)
		lifecycleevent.added(item)
		return True
	return False

def _register_utility(item, provided, ntiid, registry=None, connection=None):
	if provided.providedBy(item):
		registry = _registry(registry)
		registered = registry.queryUtility(provided, name=ntiid)
		if registered is None:
			registerUtility(registry, item, provided=provided, name=ntiid)
			notify_object_added(item, registry, connection) # get an intid
			return (True, item)
		return (False, registered)
	return (False, None)
		
def _was_utility_registered(item, item_iface, ntiid, registry=None, connection=None):
	result, _ = _register_utility(item, item_iface, ntiid, 
								  registry=registry, connection=connection)
	return result

def _load_and_register_items(item_iterface, items, registry=None, connection=None,
							 external_object_creator=create_object_from_external):
	result = []
	registry = _registry(registry)
	for ntiid, data in items.items():
		internal = external_object_creator(data)
		if _was_utility_registered(internal, item_iterface, ntiid, 
								  registry=registry, connection=connection):
			result.append(internal)
	return result

def _load_and_register_json(item_iterface, jtext, registry=None, connection=None,
							external_object_creator=create_object_from_external):
	index = simplejson.loads(prepare_json_text(jtext))
	items = index.get(ITEMS) or {}
	result = _load_and_register_items(item_iterface, items, 
									  registry=registry,
									  connection=connection,
									  external_object_creator=external_object_creator)
	return result

def _canonicalize(items, item_iface, registry):
	recorded = []
	for idx, item in enumerate(items or ()):
		ntiid = item.ntiid
		result, registered = _register_utility(item, item_iface, ntiid, registry)
		if result:
			recorded.append(item)
		else:
			items[idx] = registered # replaced w/ registered
	return recorded

## Library

def _load_and_register_slidedeck_json(jtext, registry=None, connection=None,
									  object_creator=create_object_from_external):
	result = []
	registry = _registry(registry)
	index = simplejson.loads(prepare_json_text(jtext))	
	items = index.get(ITEMS) or {}
	for ntiid, data in items.items():
		internal = object_creator(data)
		if 	INTISlide.providedBy(internal) and \
			_was_utility_registered(internal, INTISlide, ntiid, registry, connection):
			result.append(internal)
		elif INTISlideVideo.providedBy(internal) and \
			 _was_utility_registered(internal, INTISlideVideo, ntiid, registry, connection):
			result.append(internal)
		elif INTISlideDeck.providedBy(internal):
			result.extend(_canonicalize(internal.Slides, INTISlide, registry))
			result.extend(_canonicalize(internal.Videos, INTISlideVideo, registry))
			if _was_utility_registered(internal, INTISlideDeck, ntiid, registry, connection):
				result.append(internal)
	return result

def _get_data_lastModified(content_package, namespace):
	catalog = get_catalog()
	key = '%s.%s.lastModified' % (content_package.ntiid, namespace)
	result = catalog.get_last_modified(key)
	return result

def _set_data_lastModified(content_package, namespace, lastModified=0):
	catalog = get_catalog()
	key = '%s.%s.lastModified' % (content_package.ntiid, namespace)
	catalog.set_last_modified(key, lastModified)
		
def _remove_data_lastModified(content_package, namespace):
	catalog = get_catalog()
	key = '%s.%s.lastModified' % (content_package.ntiid, namespace)
	catalog.remove_last_modified(key)
	
def _register_items_when_content_changes(content_package,
										 index_iface,
										 item_iface,
										 registry=None,
										 connection=None,
										 object_creator=None,
										 catalog=None,
										 intids=None,
										 force=False):
	catalog = get_catalog() if catalog is None else catalog
	namespace = index_iface.getTaggedValue(TAG_NAMESPACE_FILE)
	sibling_key = content_package.does_sibling_entry_exist(namespace)
	if not sibling_key:
		return ()
	
	sibling_lastModified = sibling_key.lastModified
	root_lastModified = _get_data_lastModified(content_package, namespace)
	if not force and root_lastModified >= sibling_lastModified:
		return ()

	now = time.time()
	logger.info('Synchronizing %s for %s', namespace, content_package.ntiid)
	
	intids = component.queryUtility(IIntIds) if intids is None else intids
	removed = _remove_from_registry(namespace=content_package.ntiid, 
									provided=item_iface,
									registry=registry,
									catalog=catalog,
									intids=intids)

	logger.debug('%s item(s) removed from registry for %s in %s', len(removed),
				 item_iface, content_package.ntiid)
	
	index_text = content_package.read_contents_of_sibling_entry(namespace)
	if item_iface == INTISlideDeck:
		_remove_from_registry(namespace=content_package.ntiid, 
							  provided=INTISlide, 
							  registry=registry,
							  catalog=catalog,
							  intids=intids)
		
		_remove_from_registry(namespace=content_package.ntiid, 
							  provided=INTISlideVideo,
							  registry=registry,
							  catalog=catalog,
							  intids=intids)
		
		registered = _load_and_register_slidedeck_json(index_text, 
													   registry=registry,
													   connection=connection,
													   object_creator=object_creator)
	elif object_creator is not None:
		registered = _load_and_register_json(
								item_iface, index_text,
								registry=registry,
								connection=connection,
								external_object_creator=object_creator)
	else:
		registered = _load_and_register_json(
								item_iface, index_text,
								registry=registry,
								connection=connection,
								external_object_creator=create_object_from_external)
		
	logger.debug('Indexing %s registered items for %s in %s', len(registered), 
				 item_iface, content_package.ntiid)

	for item in registered:
		item.__parent__ = content_package
		item_iface = iface_of_thing(item)
		catalog.index(item, intids=intids, provided=item_iface,
					  namespace=content_package.ntiid)

	_set_data_lastModified(content_package, namespace, sibling_lastModified)
	
	logger.info('%s for %s has been synchronized in %s(s)', namespace,
				 content_package.ntiid, time.time() - now)
	
	return registered
	
def synchronize_content_package(content_package, catalog=None, force=False):
	result = []
	registry = _registry()
	connection = _connection(registry)
	for icontainer, item_iface, object_creator in INTERFACE_TUPLES:
		items = _register_items_when_content_changes(content_package, 
													 icontainer, 
													 item_iface,
													 force=force,
													 catalog=catalog,
													 registry=registry,
													 connection=connection,
													 object_creator=object_creator)
		result.extend(items or ())
	return result

def _is_global_library():
	library = component.queryUtility(IContentPackageLibrary)
	result = IGlobalContentPackageLibrary.providedBy(library)
	return result

def _update_data_when_content_changes(content_package, event):
	catalog = get_catalog()
	if catalog is not None and not _is_global_library():
		synchronize_content_package(content_package, catalog=catalog)

@component.adapter(IContentPackage, IObjectRemovedEvent)
def _clear_data_when_content_removed(content_package, event):
	catalog = get_catalog()
	if catalog is not None and not _is_global_library():
		for index_iface, item_iface, _ in INTERFACE_TUPLES:
			namespace = index_iface.getTaggedValue(TAG_NAMESPACE_FILE)
			_remove_data_lastModified(content_package, namespace)
			_remove_from_registry(namespace=content_package.ntiid, 
								  provided=item_iface,
								  catalog=catalog)
		_remove_from_registry(namespace=content_package.ntiid, 
							  provided=INTISlide,
							  catalog=catalog)
		_remove_from_registry(namespace=content_package.ntiid,
							  provided=INTISlideVideo,
							  catalog=catalog)

## Courses

def _remove_registered_lesson_overview(name, registry=None):
	## remove lesson overviews
	overview = _removed_registered(INTILessonOverview, name=name, registry=registry)
	if overview is None:
		return
	## remove all groups
	for group in overview:
		_removed_registered(INTICourseOverviewGroup, name=group.ntiid, registry=registry)
		## For each group remove anything that is not synced in the content pacakge.
		## As of 20150404 we don't have a way to edit and register common group 
		## overview items so we need to remove the old and re-register the new
		for item in group: # this shoud resolve weak refs
			iface = iface_of_thing(item)
			if iface not in PACKAGE_CONTAINER_INTERFACES:
				_removed_registered(iface, name=item.ntiid, registry=registry)
				
def _load_and_register_lesson_overview_json(jtext, registry=None, 
											validate=False, course=None):
	registry = _registry(registry)
	
	## read and parse json text
	data = simplejson.loads(prepare_json_text(jtext))
	overview = create_lessonoverview_from_external(data)
	
	## remove and register
	_remove_registered_lesson_overview(name=overview.ntiid, registry=registry)
	_register_utility(overview, INTILessonOverview, overview.ntiid, registry)

	## canonicalize group
	groups = overview.Items
	for gdx, group in enumerate(groups):
		## register course overview roup
		result, registered = _register_utility(	group, 
												INTICourseOverviewGroup,
											   	group.ntiid,
											   	registry)
		if not result: ## replace if registered before
			groups[gdx] = registered
		
		## set lineage
		registered.__parent__ = overview
			
		idx = 0
		items = group.Items
		## canonicalize item refs
		while idx < len(items):
			item = items[idx]
			## check for weak refs in case has been canonicalized
			item = item() if IWeakRef.providedBy(item) else item
			if item is None:
				del items[idx]
				continue
			
			item_iface = iface_of_thing(item)
			result, registered = _register_utility(item, 
											 	   ntiid=item.ntiid,
											  	   registry=registry,
											  	   provided=item_iface)
			
			validator = IItemRefValidator(item, None)
			is_valid = (not validate or validator is None or \
						validator.validate())
		
			if not is_valid: # don't include in the ovewview
				del items[idx]
				continue
			elif not result: # replace if registered before
				items[idx] = registered
			idx += 1

	return overview

def _get_source_lastModified(source, catalog=None):
	catalog = get_catalog() if catalog is None else catalog
	key = '%s.lastModified' % source
	result = catalog.get_last_modified(key)
	return result

def _set_source_lastModified(source, lastModified=0, catalog=None):
	catalog = get_catalog() if catalog is None else catalog
	key = '%s.lastModified' % source
	catalog.set_last_modified(key, lastModified)
	
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

def _remove_and_unindex_course_assets(containers=None, namespace=None, 
									  catalog=None, intids=None, registry=None):
	
	catalog = get_catalog() if catalog is None else catalog
	intids = component.queryUtility(IIntIds) if intids is None else intids
	
	## unregister and unindex lesson overview obects
	for item in catalog.search_objects(intids=intids, provided=INTILessonOverview, 
									   containers=containers, namespace=namespace):
		_remove_registered_lesson_overview(name=item.ntiid, registry=registry)

	if containers: ## unindex all other objects
		ids = catalog.get_references(containers=containers, namespace=namespace)
		for doc_id in list(ids or ()): # we are mutating
			catalog.remove_containers(doc_id, containers)

def _index_overview_items(items, containers=None, namespace=None, 
						  intids=None, catalog=None, node=None):
	catalog = get_catalog() if catalog is None else catalog
	for item in items:
		item = item() if IWeakRef.providedBy(item) else item
		if item is None:
			continue

		## set lesson overview NTIID on the outline node
		if INTILessonOverview.providedBy(item) and node is not None:
			node.LessonOverviewNTIID = item.ntiid
			
		item_iface = iface_of_thing(item)

		## for lesson and groups overviews index all fields
		if 	INTILessonOverview.providedBy(item) or \
			INTICourseOverviewGroup.providedBy(item):
			catalog.index(item, 
						  intids=intids, 
						  provided=item_iface,
						  namespace=namespace,
						  containers=containers)
			
			_index_overview_items(item.Items,  
								  namespace=namespace,
								  containers=containers,
								  intids=intids,
								  catalog=catalog,
								  node=node)
		else:
			catalog.index(item, 
						  intids=intids, 
						  provided=item_iface,
						  containers=containers)

def synchronize_course_lesson_overview(course, intids=None, catalog=None, force=False):
	result = []
	course_packages = get_course_packages(course)
	catalog = get_catalog() if catalog is None else catalog
	intids = component.queryUtility(IIntIds) if intids is None else intids

	registry = _registry()
	entry = ICourseCatalogEntry(course, None)
	ntiid = entry.ntiid if entry is not None else course.__name__
	name = entry.ProviderUniqueID if entry is not None else course.__name__
	
	now = time.time()
	logger.info('Synchronizing lessons overviews for %s', name)

	if ICourseSubInstance.providedBy(course):
		parent = course.__parent__.__parent__
	else:
		parent = course

	## parse and register
	nodes = _outline_nodes(course.Outline)
	for node in nodes:
		namespace = node.src ## this is ntiid based file (unique)
		for content_package in course_packages:
			sibling_key = content_package.does_sibling_entry_exist(namespace)
			if not sibling_key:
				break
			
			sibling_lastModified = sibling_key.lastModified
			root_lastModified = _get_source_lastModified(namespace, catalog)
			if not force and root_lastModified >= sibling_lastModified:
				## we want to associate the ntiid of the new course with the 
				## assets and set the lesson overview ntiid to the outline node
				objects = catalog.search_objects(namespace=namespace,
												 provided=INTILessonOverview,
												 intids=intids)
				_index_overview_items(objects,
									  namespace=namespace,
									  containers=ntiid,
									  catalog=catalog,
									  intids=intids,
									  node=node)
				continue

			## this remove all lesson overviews and overview groups
			## for specified namespace file 
			_remove_and_unindex_course_assets(namespace=namespace,
											  containers=ntiid,
											  registry=registry,
											  catalog=catalog,
											  intids=intids)
			
			logger.debug("Synchronizing %s", namespace)
			index_text = content_package.read_contents_of_sibling_entry(namespace)
			overview = _load_and_register_lesson_overview_json(	index_text, 
																validate=True,
																course=course,
																registry=registry)
			result.append(overview)
			
			## set lineage
			overview.__parent__ = parent
						
			## index
			_index_overview_items((overview,),
								  namespace=namespace,
								  containers=ntiid,
								  catalog=catalog,
								  intids=intids,
								  node=node)

			_set_source_lastModified(namespace, sibling_lastModified, catalog)

	logger.info('Lessons overviews for %s have been synchronized in %s(s)',
				 name, time.time()-now)
	return result

@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _on_course_instance_available(course, event):
	catalog = get_catalog()
	if 	catalog is not None and \
		not ILegacyCommunityBasedCourseInstance.providedBy(course): 
		synchronize_course_lesson_overview(course, catalog=catalog)

@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _clear_data_when_course_removed(course, event):
	catalog = get_catalog()
	if 	catalog is not None and \
		not ILegacyCommunityBasedCourseInstance.providedBy(course): 
		entry = ICourseCatalogEntry(course, None)
		ntiid = entry.ntiid if entry is not None else course.__name__
		_remove_and_unindex_course_assets(containers=ntiid, catalog=catalog)
