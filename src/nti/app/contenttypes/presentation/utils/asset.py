#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from zope import component
from zope import lifecycleevent

from zope.event import notify

from zope.location.location import locate
from zope.location.interfaces import ILocation

from zope.traversing.interfaces import IEtcNamespace

from ZODB.interfaces import IConnection

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import WillRemovePresentationAssetEvent

from nti.site.utils import unregisterUtility
from nti.site.site import get_component_hierarchy_names

def db_connection(registry=None):
	registry = get_registry(registry)
	result = IConnection(registry, None)
	return result

def add_2_connection(item, registry=None, connection=None):
	connection = db_connection(registry) if connection is None else connection
	if connection is not None and getattr(item, '_p_jar', None) is None:
		connection.add(item)
	result = getattr(item, '_p_jar', None) is not None
	return result

def intid_register(item, registry=None, connection=None):
	if add_2_connection(item, registry, connection):
		lifecycleevent.added(item)
		return True
	return False

def component_registry(context, provided, name=None):
	sites_names = list(get_component_hierarchy_names())
	sites_names.reverse()  # higher sites first
	name = name or getattr(context, 'ntiid', None)
	hostsites = component.getUtility(IEtcNamespace, name='hostsites')
	for site_name in sites_names:
		try:
			folder = hostsites[site_name]
			registry = folder.getSiteManager()
			if registry.queryUtility(provided, name=name) == context:
				return registry
		except KeyError:
			pass
	return get_registry()

def notify_removed(item):
	lifecycleevent.removed(item)
	if ILocation.providedBy(item):
		locate(item, None, None)

def remove_asset(item, registry=None, catalog=None):
	notify(WillRemovePresentationAssetEvent(item))
	# remove utility
	name = item.ntiid
	provided = iface_of_asset(item)
	if registry is None:
		registry = component_registry(item, provided, name=name)
	unregisterUtility(registry, provided=provided, name=name)
	# unindex
	catalog = get_library_catalog() if catalog is None else catalog
	catalog.unindex(item)
	# broadcast removed
	notify_removed(item)

def remove_lesson(item, registry=None, catalog=None):
	if isinstance(item, six.string_types):
		item = component.queryUtility(INTILessonOverview, name=item)
	if item is None:
		return
	if registry is None:
		registry = component_registry(item, INTILessonOverview, name=item.ntiid)
	catalog = get_library_catalog() if catalog is None else catalog
	# remove groups first
	for group in list(item):  # mutating
		remove_asset(group, registry, catalog)
	# remove asset
	remove_asset(item, registry, catalog)
