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

from zope.lifecycleevent import IObjectRemovedEvent

from ZODB.interfaces import IConnection

from nti.app.products.courseware.utils import get_parent_course
from nti.app.products.courseware.interfaces import ILegacyCommunityBasedCourseInstance

from nti.contentlibrary.indexed_data import get_catalog
from nti.contentlibrary.indexed_data import get_registry

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import	ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceAvailableEvent

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.utils import create_lessonoverview_from_external

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_provider_safe
from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

from nti.wref.interfaces import IWeakRef

from .interfaces import IItemRefValidator

from . import iface_of_thing

ITEMS = StandardExternalFields.ITEMS

def prepare_json_text(s):
	result = unicode(s, 'utf-8') if isinstance(s, bytes) else s
	return result

def _removed_registered(provided, name, intids=None, registry=None, catalog=None):
	registry = get_registry(registry)
	registered = registry.queryUtility(provided, name=name)
	intids = component.queryUtility(IIntIds) if intids is None else intids
	if registered is not None:
		catalog = get_catalog() if catalog is None else catalog
		catalog.unindex(registered, intids=intids)
		unregisterUtility(registry, provided=provided, name=name)
		intids.unregister(registered, event=False)
	return registered

def _db_connection(registry=None):
	registry = get_registry(registry)
	result = IConnection(registry, None)
	return result

def intid_register(item, registry, intids=None, connection=None):
	intids = component.queryUtility(IIntIds) if intids is None else intids
	connection = _db_connection(registry) if connection is None else connection
	if connection is not None:
		connection.add(item)
		intids.register(item, event=False)
		return True
	return False

def _register_utility(item, provided, ntiid, registry=None, intids=None, connection=None):
	if provided.providedBy(item):
		registry = get_registry(registry)
		registered = registry.queryUtility(provided, name=ntiid)
		if registered is None:
			assert is_valid_ntiid_string(ntiid), "invalid NTIID %s" % ntiid
			registerUtility(registry, item, provided=provided, name=ntiid)
			intid_register(item, registry, intids, connection)
			return (True, item)
		return (False, registered)
	return (False, None)

# Courses

PACKAGE_CONTAINER_INTERFACES = (INTIAudio, INTIVideo, INTITimeline,
								INTISlideDeck, INTIRelatedWorkRef)

def _remove_registered_course_overview(name=None, registry=None, course=None):
	result = 0
	group = _removed_registered(INTICourseOverviewGroup, name=name, registry=registry)
	if group is not None:
		result += 1 

	container = IPresentationAssetContainer(course, None) or {}
	container.pop(name, None)

	# For each group remove anything that is not synced in the content pacakge.
	# As of 20150404 we don't have a way to edit and register common group
	# overview items so we need to remove the old and re-register the new
	for item in group or ():  # this shoud resolve weak refs
		iface = iface_of_thing(item)
		if iface not in PACKAGE_CONTAINER_INTERFACES:
			ntiid = item.ntiid
			if _removed_registered(iface, name=ntiid, registry=registry) is not None:
				result += 1
			container.pop(item.ntiid, None)
	return result

def _remove_registered_lesson_overview(name, registry=None, course=None):
	container = IPresentationAssetContainer(course, None) or {}
	container.pop(name, None)

	# remove lesson overviews
	overview = _removed_registered(INTILessonOverview, name=name, registry=registry)
	if overview is None:
		return 0

	result = 1 # count overview
	# remove all groups
	for group in overview:
		result += _remove_registered_course_overview(name=group.ntiid,
										   			 registry=registry,
										   			 course=course)
	return result

def _load_and_register_lesson_overview_json(jtext, registry=None, ntiid=None,
											validate=False, course=None):
	registry = get_registry(registry)

	# read and parse json text
	data = simplejson.loads(prepare_json_text(jtext))
	overview = create_lessonoverview_from_external(data, notify=False)

	# remove and register
	_remove_registered_lesson_overview(name=overview.ntiid,
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

def _remove_and_unindex_course_assets(container_ntiids=None, namespace=None,
									  catalog=None, intids=None,
									  registry=None, course=None):

	catalog = get_catalog() if catalog is None else catalog
	intids = component.queryUtility(IIntIds) if intids is None else intids
	
	result = 0
	# unregister and unindex lesson overview obects
	for item in catalog.search_objects(intids=intids, provided=INTILessonOverview,
									   container_ntiids=container_ntiids,
									   namespace=namespace):
		result += _remove_registered_lesson_overview(name=item.ntiid,
										   			 registry=registry,
										   			 course=course)

	if container_ntiids:  # unindex all other objects
		container = IPresentationAssetContainer(course, None) or {}
		objs = catalog.search_objects(container_ntiids=container_ntiids,
									  namespace=namespace, intids=intids)
		for obj in list(objs):  # we are mutating
			doc_id = intids.queryId(obj)
			if doc_id is not None:
				catalog.remove_containers(doc_id, container_ntiids)
			container.pop(obj.ntiid, None)
	return result
remove_and_unindex_course_assets = _remove_and_unindex_course_assets

def _index_overview_items(items, container_ntiids=None, namespace=None,
						  intids=None, catalog=None, node=None, course=None):
	catalog = get_catalog() if catalog is None else catalog
	container = IPresentationAssetContainer(course, None)
	for item in items:
		item = item() if IWeakRef.providedBy(item) else item
		if item is None:
			continue

		if container is not None:
			container[item.ntiid] = item

		# set lesson overview NTIID on the outline node
		if INTILessonOverview.providedBy(item) and node is not None:
			node.LessonOverviewNTIID = item.ntiid

		# for lesson and groups overviews index all fields
		if 	INTILessonOverview.providedBy(item) or \
			INTICourseOverviewGroup.providedBy(item):
			catalog.index(item,
						  intids=intids,
						  namespace=namespace,
						  container_ntiids=container_ntiids)

			_index_overview_items(item.Items,
								  namespace=namespace,
								  container_ntiids=container_ntiids,
								  intids=intids,
								  catalog=catalog,
								  node=node,
								  course=course)
		else:
			# CS: We don't index items in groups with the namespace
			# because and item can be in different groups with different
			# namespace 
			catalog.index(item,
						  intids=intids,
						  container_ntiids=container_ntiids)

def synchronize_course_lesson_overview(course, intids=None, catalog=None):
	result = []
	course_packages = get_course_packages(course)
	catalog = get_catalog() if catalog is None else catalog
	intids = component.queryUtility(IIntIds) if intids is None else intids

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
	nodes = _outline_nodes(course.Outline)
	for node in nodes:
		namespace = node.src  # this is ntiid based file (unique)
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
			_remove_and_unindex_course_assets(namespace=namespace,
											  container_ntiids=ntiid,
											  registry=registry,
											  catalog=catalog,
											  intids=intids,
											  course=course)

			logger.debug("Synchronizing %s", namespace)
			index_text = content_package.read_contents_of_sibling_entry(namespace)
			overview = _load_and_register_lesson_overview_json(index_text,
															   validate=True,
															   course=course,
															   ntiid=ref_ntiid,
															   registry=registry)
			result.append(overview)

			# set lineage
			overview.__parent__ = node

			# index
			_index_overview_items((overview,),
								  namespace=namespace,
								  container_ntiids=ntiid,
								  catalog=catalog,
								  intids=intids,
								  node=node,
								  course=course)

			_set_source_lastModified(namespace, sibling_lastModified, catalog)

	logger.info('Lessons overviews for %s have been synchronized in %s(s)',
				 name, time.time() - now)
	return result

@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _on_course_instance_available(course, event):
	catalog = get_catalog()
	if catalog is not None and not ILegacyCommunityBasedCourseInstance.providedBy(course):
		synchronize_course_lesson_overview(course, catalog=catalog)

def _clear_course_assets(course):
	container = IPresentationAssetContainer(course, None)
	if container is not None:
		container.clear()

@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _clear_data_when_course_removed(course, event):
	catalog = get_catalog()
	if catalog is not None and not ILegacyCommunityBasedCourseInstance.providedBy(course):
		_clear_course_assets(course)
		entry = ICourseCatalogEntry(course, None)
		ntiid = entry.ntiid if entry is not None else course.__name__
		_remove_and_unindex_course_assets(container_ntiids=ntiid, catalog=catalog)
