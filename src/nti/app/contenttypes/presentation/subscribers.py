#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import simplejson

from zope import component

from zope.annotation.interfaces import IAnnotations

from zope.lifecycleevent import IObjectRemovedEvent

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IGlobalContentPackageLibrary

from nti.contentlibrary.indexed_data.interfaces import TAG_NAMESPACE_FILE
from nti.contentlibrary.indexed_data.interfaces import IAudioIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IVideoIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import ITimelineIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import ISlideDeckIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IRelatedContentIndexedDataContainer

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIRelatedWork

from nti.contenttypes.presentation.utils import create_object_from_external

from nti.externalization.interfaces import StandardExternalFields

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

def _remove_from_registry_with_index(package, index_interface, item_iterface,
									 registry=None):
	registry = _registry(registry)
	def _recur(unit):
		container = index_interface(unit, None) or ()
		for ntiid in container:
			registry.unregisterUtility(provided=item_iterface, name=ntiid)
		for child in unit.children:
			_recur(child)
	_recur(package)

def _remove_from_registry_with_interface(package, item_iterface, registry=None):
	result = []
	registry = _registry(registry)
	for name , utility in list(registry.getUtilitiesFor(item_iterface)):
		if getattr(utility, 'content_package_ntiid', None) == package.ntiid:
			result.append(utility)
			registry.unregisterUtility(provided=item_iterface, name=name)
	return result

def _register_utility(item, item_iface, ntiid, registry):
	if 	item_iface.providedBy(item) and \
		registry.queryUtility(item_iface, name=ntiid) is None:
		registry.registerUtility(item,
								 provided=item_iface,
								 name=ntiid,
								 event=False)
		return True
	return False
		
def _load_and_register_items(item_iterface, items, registry=None):
	result = []
	registry = _registry(registry)
	for ntiid, data in items.items():
		internal = create_object_from_external(data)
		if _register_utility(internal, item_iterface, ntiid, registry):
			result.append(internal)
	return result

def _load_and_register_json(item_iterface, jtext, registry=None):
	index = simplejson.loads(prepare_json_text(jtext))
	items = index.get(ITEMS) or {}
	result = _load_and_register_items(item_iterface, items, registry)
	return result

def _canonicalize(items, item_iface, registry):
	result = []
	for idx, item in enumerate(items or ()):
		ntiid = item.ntiid
		registered = registry.queryUtility(item_iface, name=ntiid)
		if registered is None:
			registry.registerUtility(item,
							  		 provided=item_iface,
							  		 name=ntiid,
							  		 event=False)
			result.append(item)
		else:
			items[idx] = registered # replaced w/ registered
	return result

def _load_and_register_slidedeck_json(jtext, registry=None):
	result = []
	registry = _registry(registry)
	index = simplejson.loads(prepare_json_text(jtext))
	items = index.get(ITEMS) or {}
	for ntiid, data in items.items():
		internal = create_object_from_external(data)
		if 	INTISlide.providedBy(internal) and \
			_register_utility(internal, INTISlide, ntiid, registry):
			result.append(internal)
		elif INTISlideVideo.providedBy(internal) and \
			 _register_utility(internal, INTISlideVideo, ntiid, registry):
			result.append(internal)
		elif INTISlideDeck.providedBy(internal):
			result.extend(_canonicalize(internal.Slides, INTISlide, registry))
			result.extend(_canonicalize(internal.Videos, INTISlideVideo, registry))
			if _register_utility(internal, INTISlideDeck, ntiid, registry):
				result.append(internal)
	return result

def _get_data_lastModified(content_package, item_iface):
	annotations = IAnnotations(content_package)
	key = '%s.%s.lastModified' % (item_iface.__module__, item_iface.__name__)
	try:
		result = annotations[key]
	except KeyError:
		result = 0
	return result

def _set_data_lastModified(content_package, item_iface, lastModified=0):
	annotations = IAnnotations(content_package)
	key = '%s.%s.lastModified' % (item_iface.__module__, item_iface.__name__)
	annotations[key] = lastModified

def _register_items_when_content_changes(content_package, index_iface, item_iface):
	namespace = index_iface.getTaggedValue(TAG_NAMESPACE_FILE)
	sibling_key = content_package.does_sibling_entry_exist(namespace)
	if not sibling_key:
		return
	
	sibling_lastModified = sibling_key.lastModified
	root_lastModified = _get_data_lastModified(content_package, item_iface)
	if root_lastModified >= sibling_lastModified:
		return
	
	_remove_from_registry_with_interface(content_package, item_iface)

	index_text = content_package.read_contents_of_sibling_entry(namespace)
	if item_iface == INTISlideDeck:
		registered = _load_and_register_slidedeck_json(index_text)
	else:
		registered = _load_and_register_json(item_iface, index_text)
		
	for item in registered:
		item.content_package_ntiid = content_package.ntiid # save package source

	_set_data_lastModified(content_package, item_iface, sibling_lastModified)
	
def _update_data_when_content_changes(content_package, event):
	for icontainer, item_iface in INTERFACE_PAIRS:
		_register_items_when_content_changes(content_package, icontainer, item_iface)

@component.adapter(IContentPackage, IObjectRemovedEvent)
def _clear_data_when_content_changes(content_package, event):
	for _, item_iface in INTERFACE_PAIRS:
		_remove_from_registry_with_interface(content_package, item_iface)
	_remove_from_registry_with_interface(content_package, INTISlide)
	_remove_from_registry_with_interface(content_package, INTISlideVideo)
