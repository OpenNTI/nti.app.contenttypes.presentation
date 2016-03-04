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

from zope import component
from zope import lifecycleevent

from zope.event import notify

from zope.interface.interface import InterfaceClass

from zope.location.interfaces import ILocation

from zope.location.location import locate

from zope.traversing.interfaces import IEtcNamespace

from ZODB.interfaces import IConnection

from nti.common.random import generate_random_hex_string

from nti.common.time import time_to_64bit_int

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import WillRemovePresentationAssetEvent

from nti.contenttypes.presentation.lesson import NTILessonOverView

from nti.externalization.oids import to_external_ntiid_oid

from nti.intid.common import addIntId

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

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

def intid_register(item, registry=None, connection=None, event=True):
	if add_2_connection(item, registry, connection):
		if event:
			lifecycleevent.added(item)
		else:
			addIntId(item)
		return True
	return False

def get_registry_by_name(name):
	hostsites = component.getUtility(IEtcNamespace, name='hostsites')
	try:
		folder = hostsites[name]
		registry = folder.getSiteManager()
		return registry
	except KeyError:
		pass
	return None
registry_by_name = get_registry_by_name

def get_component_site(context, provided, name=None):
	result = None
	folder = find_interface(context, IHostPolicyFolder, strict=False)
	if folder is None:
		sites_names = get_component_hierarchy_names()
		name = name or getattr(context, 'ntiid', None)
		hostsites = component.getUtility(IEtcNamespace, name='hostsites')
		for idx in range(len(sites_names) - 1, -1, -1):  # higher sites first
			try:
				site_name = sites_names[idx]
				folder = hostsites[site_name]
				registry = folder.getSiteManager()
				if registry.queryUtility(provided, name=name) == context:
					result = site_name
					break
			except KeyError:
				pass
	else:
		result = folder.__name__
	return result
component_site = get_component_site

def get_component_registry(context, provided, name=None):
	site_name = component_site(context, provided, name)
	if site_name:
		folder = component.getUtility(IEtcNamespace, name='hostsites')[site_name]
		return folder.getSiteManager()
	return get_registry()
component_registry = get_component_registry

def notify_removed(item):
	lifecycleevent.removed(item)
	if ILocation.providedBy(item):
		locate(item, None, None)

def get_registry_4_item(item, provided, name, registry=None):
	if registry is None:
		registry = component_registry(item, provided, name=name)
	return registry
registry4 = get_registry_4_item

def remove_asset(item, registry=None, catalog=None):
	notify(WillRemovePresentationAssetEvent(item))
	# remove utility
	name = item.ntiid
	provided = iface_of_asset(item)
	registry = get_registry_4_item(item, provided, name, registry=registry)
	unregisterUtility(registry, provided=provided, name=name)
	# unindex
	catalog = get_library_catalog() if catalog is None else catalog
	catalog.unindex(item)
	# broadcast removed
	notify_removed(item)  # remove intid

def remove_mediaroll(item, registry=None, catalog=None):
	if isinstance(item, six.string_types):
		item = component.queryUtility(INTIMediaRoll, name=item)
	if item is None:
		return
	name = item.ntiid
	registry = get_registry_4_item(item, INTIMediaRoll, name, registry=registry)
	catalog = get_library_catalog() if catalog is None else catalog
	# remove mediarefs first
	for media in list(item):  # mutating
		remove_asset(media, registry, catalog)
	# remove roll
	remove_asset(item, registry, catalog)

def remove_group(group, registry=None, catalog=None, package=False):
	if isinstance(group, six.string_types):
		group = component.queryUtility(INTICourseOverviewGroup, name=group)
	if group is None:
		return
	name = group.ntiid
	registry = get_registry_4_item(group, INTICourseOverviewGroup, name, registry=registry)
	catalog = get_library_catalog() if catalog is None else catalog
	# remove items first
	for item in list(group):  # mutating
		provided = iface_of_asset(item)
		if INTIMediaRoll.providedBy(item):
			remove_mediaroll(item, registry, catalog)
		elif package or provided not in PACKAGE_CONTAINER_INTERFACES:
			remove_asset(item, registry, catalog)
	# remove groups
	remove_asset(group, registry, catalog)

def remove_lesson(item, registry=None, catalog=None, package=False):
	if isinstance(item, six.string_types):
		item = component.queryUtility(INTILessonOverview, name=item)
	if item is None:
		return
	name = item.ntiid
	registry = get_registry_4_item(item, INTILessonOverview, name, registry=registry)
	catalog = get_library_catalog() if catalog is None else catalog
	# remove groups first
	for group in list(item):  # mutating
		remove_group(group, registry, catalog, package=package)
	# remove asset
	remove_asset(item, registry, catalog)

def remove_presentation_asset(item, registry=None, catalog=None, package=False):
	if INTILessonOverview.providedBy(item):
		remove_lesson(item, registry, catalog, package=package)
	elif INTICourseOverviewGroup.providedBy(item):
		remove_group(item, registry, catalog, package=package)
	elif INTIMediaRoll.providedBy(item):
		remove_mediaroll(item, registry, catalog)
	else:
		remove_asset(item, registry, catalog)

def make_asset_ntiid(nttype, creator=SYSTEM_USER_ID, base=None, extra=None):
	if type(nttype) == InterfaceClass:
		nttype = nttype.__name__[1:]

	current_time = time_to_64bit_int(time.time())
	creator = getattr(creator, 'username', creator)
	provider = get_provider(base) or 'NTI' if base else 'NTI'

	specific_base = get_specific(base) if base else None
	if specific_base:
		specific_base += '.%s.%s' % (creator, current_time)
	else:
		specific_base = '%s.%s' % (creator, current_time)

	if extra:
		specific_base = specific_base + ".%s" % extra
	specific = make_specific_safe(specific_base)

	ntiid = make_ntiid(nttype=nttype,
					   base=base,
					   provider=provider,
					   specific=specific)
	return ntiid

def get_course_for_node(node):
	course = find_interface(node, ICourseInstance, strict=False)
	return course
course_for_node = get_course_for_node

def create_lesson_4_node(node, ntiid=None, registry=None, catalog=None, sites=None):
	creator = getattr(node, 'creator', None) or SYSTEM_USER_ID
	creator = getattr(creator, 'username', creator)
	if not ntiid:
		extra = generate_random_hex_string(6)
		ntiid = make_asset_ntiid(nttype=INTILessonOverview,
								 creator=creator,
								 base=node.ntiid,
								 extra=extra)

	result = NTILessonOverView(ntiid=ntiid, title=getattr(node, 'title', None))
	result.__parent__ = node
	result.creator = creator

	# XXX If there is no lesson set it to the overview
	if hasattr(node, 'ContentNTIID') and not node.ContentNTIID:
		node.ContentNTIID = ntiid

	# XXX: set lesson overview ntiid
	# At his point is very likely that LessonOverviewNTIID,
	# ContentNTIID are simply alias fields. All of them
	# are kept so long as we have manual sync and BWC
	node.LessonOverviewNTIID = ntiid

	# XXX: if registry is specified register the new node
	if registry is not None:
		# register lesson
		intid_register(result, registry=registry, event=False)
		registerUtility(registry,
						result,
						provided=INTILessonOverview,
						name=ntiid)

		# XXX: set the src field to be unique for indexing see MediaByOutlineNode
		if not getattr(node, 'src', None):
			node.src = to_external_ntiid_oid(result)

		# XXX index lesson
		course = get_course_for_node(node)
		if course is not None:
			entry = ICourseCatalogEntry(course)
			container = IPresentationAssetContainer(course)
			ntiids = (entry.ntiid,)  # container ntiid
			container[ntiid] = result  # add to container
		else:
			ntiids = None
		catalog = get_library_catalog() if catalog is None else catalog
		catalog.index(result, container_ntiids=ntiids,
					  namespace=node.src, sites=sites)

	# lesson is ready
	return result
