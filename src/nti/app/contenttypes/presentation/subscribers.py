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

from nti.common.functional import identity

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IGlobalContentPackageLibrary

from nti.contentlibrary.indexed_data.interfaces import TAG_NAMESPACE_FILE
from nti.contentlibrary.indexed_data.interfaces import IAudioIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IVideoIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import ITimelineIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import ISlideDeckIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IRelatedContentIndexedDataContainer

from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
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

def _remove_from_registry_with_index(pacakge, index_interface, item_iterface,
                                     registry=None):
	registry = _registry(registry)
	def _recur(unit):
		container = index_interface(unit, None) or ()
		for ntiid in container:
			registry.unregisterUtility(item_iterface, name=ntiid)
		for child in unit.children:
			_recur(child)
	_recur(pacakge)

def _remove_from_registry_with_interface(pacakge, item_iterface, registry=None):
	registry = _registry(registry)
	for name , utility in list(registry.getAllUtilitiesRegisteredFor(item_iterface)):
		if getattr(utility, 'content_pacakge_ntiid', None) == pacakge.ntiid:
			registry.unregisterUtility(item_iterface, name=name)

def _load_and_register_json(item_iterface, jtext, canonicalizer=identity, registry=None):
	result = []
	registry = _registry(registry)
	index = simplejson.loads(prepare_json_text(jtext))
	items = index.get(ITEMS) or {}
	for ntiid, data in items.items():
		internal = create_object_from_external(data)
		internal = canonicalizer(internal)
		registry.registerUtility( internal,
								  provided=item_iterface,
								  name=ntiid,
								  event=False)
		result.append(internal)
	return result

def _register_items_when_content_changes(content_package, index_iface, item_iface):
	namespace = index_iface.getTaggedValue(TAG_NAMESPACE_FILE)
	sibling_key = content_package.does_sibling_entry_exist(namespace)
	if not sibling_key:
		return
	
	root_index_container = index_iface(content_package)
	if root_index_container.lastModified >= sibling_key.lastModified:
		return
	
		
	_remove_from_registry_with_interface(content_package, item_iface)
	index_text = content_package.read_contents_of_sibling_entry(namespace)
	registered = _load_and_register_json(item_iface, index_text)
	for item in registered:
		item.content_pacakge_ntiid = content_package.ntiid # save pacakge source
	
def _update_data_when_content_changes(content_package, event):
	for icontainer, item_iface in INTERFACE_PAIRS:
		_register_items_when_content_changes(content_package,icontainer, item_iface)

def _clear_data_when_content_changes(content_package, event):
	for _, item_iface in INTERFACE_PAIRS:
		_remove_from_registry_with_interface(content_package, item_iface)
