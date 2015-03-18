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

from zope.annotation.interfaces import IAnnotations

from zope import lifecycleevent
from zope.lifecycleevent import IObjectRemovedEvent

from ZODB.interfaces import IConnection

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

from nti.contenttypes.presentation import GROUP_OVERVIEWABLE_INTERFACES
from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIRelatedWork
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.contenttypes.presentation.utils import create_object_from_external
from nti.contenttypes.presentation.utils import create_ntivideo_from_external
from nti.contenttypes.presentation.utils import create_relatedwork_from_external
from nti.contenttypes.presentation.utils import create_lessonoverview_from_external

from nti.externalization.interfaces import StandardExternalFields

from .index import search_by
from .index import index_item
from .index import unindex_item
from .interfaces import IItemRefValidator

ITEMS = StandardExternalFields.ITEMS

INTERFACE_PAIRS = ( (IAudioIndexedDataContainer, INTIAudio),
					(IVideoIndexedDataContainer, INTIVideo), 
					(ITimelineIndexedDataContainer, INTITimeline),
					(ISlideDeckIndexedDataContainer, INTISlideDeck),
					(IRelatedContentIndexedDataContainer, INTIRelatedWork) )

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

def _iface_of_thing(item):
	for iface in ALL_PRESENTATION_ASSETS_INTERFACES:
		if iface.providedBy(item):
			return iface
	return None

def _remove_from_registry_with_interface(parent_ntiid, item_iterface, registry=None, intids=None):
	intids = component.queryUtility(IIntIds) if intids is None else intids
	if intids is not None:
		result = []
		registry = _registry(registry)
		for docid in search_by(item_iterface, parent_ntiid):
			utility = intids.queryObject(docid)
			ntiid = getattr(utility, 'ntiid', None)
			if ntiid and utility is not None:
				unindex_item(docid)
				result.append(utility)
				registry.unregisterUtility(provided=item_iterface, name=ntiid)
				lifecycleevent.removed(utility) # remove fron intids
			elif not utility:
				intids.forceUnregister(docid)
	else:
		result = ()
	return result

def _register_utility(item, item_iface, ntiid, registry):
	if item_iface.providedBy(item):
		registered = registry.queryUtility(item_iface, name=ntiid)
		if registered is None:
			registry.registerUtility(item,
									 provided=item_iface,
									 name=ntiid,
									 event=False)
			connection = IConnection(registry, None)
			if connection is not None:
				connection.add(item)
				lifecycleevent.added(item) # get an intid
			return (True, item)
		return (False, registered)
	return (False, None)
		
def _was_utility_registered(item, item_iface, ntiid, registry):
	result, _ = _register_utility(item, item_iface, ntiid, registry)
	return result

def _load_and_register_items(item_iterface, items, registry=None, 
							 external_object_creator=create_object_from_external):
	result = []
	registry = _registry(registry)
	for ntiid, data in items.items():
		internal = external_object_creator(data)
		if _was_utility_registered(internal, item_iterface, ntiid, registry):
			result.append(internal)
	return result

def _load_and_register_json(item_iterface, jtext, registry=None,
							external_object_creator=create_object_from_external):
	index = simplejson.loads(prepare_json_text(jtext))
	items = index.get(ITEMS) or {}
	result = _load_and_register_items(item_iterface, items, registry,
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

def _load_and_register_slidedeck_json(jtext, registry=None, 
									  object_creator=create_object_from_external):
	result = []
	registry = _registry(registry)
	index = simplejson.loads(prepare_json_text(jtext))
	items = index.get(ITEMS) or {}
	for ntiid, data in items.items():
		internal = object_creator(data)
		if 	INTISlide.providedBy(internal) and \
			_was_utility_registered(internal, INTISlide, ntiid, registry):
			result.append(internal)
		elif INTISlideVideo.providedBy(internal) and \
			 _was_utility_registered(internal, INTISlideVideo, ntiid, registry):
			result.append(internal)
		elif INTISlideDeck.providedBy(internal):
			result.extend(_canonicalize(internal.Slides, INTISlide, registry))
			result.extend(_canonicalize(internal.Videos, INTISlideVideo, registry))
			if _was_utility_registered(internal, INTISlideDeck, ntiid, registry):
				result.append(internal)
	return result

def _get_data_lastModified(context, item_iface):
	annotations = IAnnotations(context)
	key = '%s.%s.lastModified' % (item_iface.__module__, item_iface.__name__)
	try:
		result = annotations[key]
	except KeyError:
		result = 0
	return result

def _set_data_lastModified(context, item_iface, lastModified=0):
	annotations = IAnnotations(context)
	key = '%s.%s.lastModified' % (item_iface.__module__, item_iface.__name__)
	annotations[key] = lastModified
		
def _register_items_when_content_changes(content_package,
										 index_iface,
										 item_iface,
										 intids=None):

	namespace = index_iface.getTaggedValue(TAG_NAMESPACE_FILE)
	sibling_key = content_package.does_sibling_entry_exist(namespace)
	if not sibling_key:
		return ()
	
	sibling_lastModified = sibling_key.lastModified
	root_lastModified = _get_data_lastModified(content_package, item_iface)
	if root_lastModified >= sibling_lastModified:
		return ()
	
	logger.info('Synchronizing %s for %s', namespace, content_package.ntiid)
	
	_remove_from_registry_with_interface(content_package.ntiid, item_iface)

	index_text = content_package.read_contents_of_sibling_entry(namespace)
	if item_iface == INTISlideDeck:
		_remove_from_registry_with_interface(content_package.ntiid, INTISlide)
		_remove_from_registry_with_interface(content_package.ntiid, INTISlideVideo)
		registered = _load_and_register_slidedeck_json(index_text)
	elif item_iface == INTIVideo:
		registered = _load_and_register_json(
								item_iface, index_text,
								external_object_creator=create_ntivideo_from_external)
	elif item_iface == INTIRelatedWork:
		registered = _load_and_register_json(
								item_iface, index_text,
								external_object_creator=create_relatedwork_from_external)
	else:
		registered = _load_and_register_json(item_iface, index_text)
		
	intids = component.queryUtility(IIntIds) if intids is None else intids
	for item in registered:
		item.__parent__ = content_package
		if intids is not None: # none in some tests
			docid = intids.getId(item)
			item_iface = _iface_of_thing(item)
			index_item(docid, item_iface, parents=(content_package.ntiid,))

	_set_data_lastModified(content_package, item_iface, sibling_lastModified)
	
	logger.info('%s for %s has been synchronized', namespace, content_package.ntiid)
	
	return registered
	
def synchronize_content_package(content_package):
	result = []
	for icontainer, item_iface in INTERFACE_PAIRS:
		items = _register_items_when_content_changes(content_package, 
													 icontainer, 
													 item_iface)
		result.extend(items or ())
	return result

def _update_data_when_content_changes(content_package, event):
	synchronize_content_package(content_package)

@component.adapter(IContentPackage, IObjectRemovedEvent)
def _clear_data_when_content_removed(content_package, event):
	for _, item_iface in INTERFACE_PAIRS:
		_remove_from_registry_with_interface(content_package.ntiid, item_iface)
	_remove_from_registry_with_interface(content_package.ntiid, INTISlide)
	_remove_from_registry_with_interface(content_package.ntiid, INTISlideVideo)

## Courses

def _load_and_register_lesson_overview_json(jtext, registry=None, validate=False):
	recorded = []
	registry = _registry(registry)
	
	## read and parse json text
	data = simplejson.loads(prepare_json_text(jtext))
	overview = create_lessonoverview_from_external(data)
	if _was_utility_registered(overview, INTILessonOverview, overview.ntiid, registry):
		recorded.append(overview)

	## canonicalize group
	groups = overview.Items
	for gdx, group in enumerate(groups):
		## register course overview roup
		result, registered = _register_utility(	group, 
												INTICourseOverviewGroup,
											   	group.ntiid,
											   	registry)
		if result:
			recorded.append(group)
		else:
			groups[gdx] = registered

		## canonicalize item refs
		idx = 0
		items = group.Items
		while idx < len(items):
			item = items[idx]
			item_iface = _iface_of_thing(item)
			result, registered = _register_utility(	item, 
													item_iface,
											   		item.ntiid,
											   		registry)
			if result:
				validator = IItemRefValidator(item, None)
				is_valid = (not validate or validator is None or \
							validator.validate())
				if is_valid:
					recorded.append(item)
				else:
					del items[idx]
					continue
			else:
				items[idx] = registered
			idx += 1
	return recorded

def _get_source_lastModified(context, source):
	annotations = IAnnotations(context)
	try:
		key = '%s.lastModified' % source
		result = annotations[key]
	except KeyError:
		result = 0
	return result

def _set_source_lastModified(context, source, lastModified=0):
	annotations = IAnnotations(context)
	key = '%s.lastModified' % source
	annotations[key] = lastModified
	
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

def _remove_and_unindex_course_assets(parent_key): 
	## Order matters
	for item_iface in GROUP_OVERVIEWABLE_INTERFACES:
		_remove_from_registry_with_interface(parent_key, item_iface)
	_remove_from_registry_with_interface(parent_key, INTICourseOverviewGroup)
	_remove_from_registry_with_interface(parent_key, INTILessonOverview)
	
def synchronize_course_lesson_overview(course, intids=None):
	result = []
	course_packages = get_course_packages(course)
	intids = component.queryUtility(IIntIds) if intids is None else intids

	entry = ICourseCatalogEntry(course, None)
	ntiid = entry.ntiid if entry is not None else course.__name__
	name = entry.ProviderUniqueID if entry is not None else course.__name__
	
	now = time.time()
	logger.info('Synchronizing lessons overviews for %s', name)

	## CS: 20150317: Use the parent course to store the last modified date of the 
	## source files. This works b/c currently subinstances  share the same
	## current content pacakge bundle
	if ICourseSubInstance.providedBy(course):
		parent = course.__parent__.__parent__
	else:
		parent = course
	
	## parse and register
	nodes = _outline_nodes(course.Outline)
	for node in nodes:
		namespace = node.src
		for content_package in course_packages:
			sibling_key = content_package.does_sibling_entry_exist(namespace)
			if not sibling_key:
				break
			
			sibling_lastModified = sibling_key.lastModified
			root_lastModified = _get_source_lastModified(parent, namespace)
			if root_lastModified >= sibling_lastModified:
				break
			
			_remove_and_unindex_course_assets(namespace)
			
			logger.debug("Synchronizing %s", namespace)
			index_text = content_package.read_contents_of_sibling_entry(namespace)
			items = _load_and_register_lesson_overview_json(index_text, validate=True)
			result.extend(items)
			
			_set_source_lastModified(parent, namespace, sibling_lastModified)

			for item in items:
				if intids is not None: # none in some tests
					docid = intids.getId(item)
					item_iface = _iface_of_thing(item)
					index_item(docid, item_iface, parents=(namespace, ntiid))
				if INTILessonOverview.providedBy(item):
					item.__parent__ = parent

	logger.info('Lessons overviews for %s have been synchronized %s(s)',
				 name, time.time()-now)
	return result

@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _on_course_instance_available(course, event):
	synchronize_course_lesson_overview(course)

@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _clear_data_when_course_removed(course, event):
	entry = ICourseCatalogEntry(course, None)
	ntiid = entry.ntiid if entry is not None else course.__name__
	_remove_and_unindex_course_assets(ntiid)
