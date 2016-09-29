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

from ZODB.interfaces import IConnection

from plone.namedfile.interfaces import INamed as IPloneNamed

from nti.app.products.courseware.resources.utils import is_internal_file_link
from nti.app.products.courseware.resources.utils import get_file_from_external_link

from nti.common.file import safe_filename

from nti.common.random import generate_random_hex_string

from nti.common.string import to_unicode

from nti.coremetadata.interfaces import SYSTEM_USER_NAME

from nti.contentlibrary.indexed_data import get_site_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTIDocketAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTICourseOverviewSpacer
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import WillRemovePresentationAssetEvent

from nti.contenttypes.presentation.lesson import NTILessonOverView

from nti.externalization.oids import to_external_ntiid_oid

from nti.intid.common import addIntId

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.site.hostpolicy import get_host_site

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

from nti.zodb.containers import time_to_64bit_int

NOT_ALLOWED_IN_REGISTRY_REFERENCES = (IAssetRef, INTICourseOverviewSpacer)

def allowed_in_registry(provided):
	for interface in NOT_ALLOWED_IN_REGISTRY_REFERENCES:
		if provided is not None and provided.isOrExtends(interface):
			return False
	return True

def get_db_connection(registry=None):
	registry = get_site_registry(registry)
	if registry == component.getGlobalSiteManager():
		result = None
	else:
		result = IConnection(registry)
	return result
db_connection = get_db_connection

def add_2_connection(item, registry=None, connection=None):
	connection = get_db_connection(registry) if connection is None else connection
	if connection is not None and getattr(item, '_p_jar', None) is None:
		connection.add(item)
	return getattr(item, '_p_jar', None) is not None

def intid_register(item, registry=None, connection=None, event=True):
	if add_2_connection(item, registry, connection):
		if event:
			lifecycleevent.added(item)
		else:
			addIntId(item)
		return True
	return False

def get_registry_by_name(name):
	folder = get_host_site(name, safe=True)
	return folder.getSiteManager() if folder is not None else None
registry_by_name = get_registry_by_name

def get_component_site(context, provided, name=None):
	result = None
	folder = find_interface(context, IHostPolicyFolder, strict=False)
	if folder is None:
		sites_names = get_component_hierarchy_names()
		name = name or getattr(context, 'ntiid', None)
		for idx in range(len(sites_names) - 1, -1, -1):  # higher sites first
			site_name = sites_names[idx]
			registry = get_registry_by_name(site_name)
			if 		registry is not None \
				and registry.queryUtility(provided, name=name) == context:
				result = site_name
				break
	else:
		result = folder.__name__
	return result
component_site = get_component_site

def get_component_registry(context, provided, name=None):
	site_name = component_site(context, provided, name)
	if site_name:
		return get_registry_by_name(site_name)
	return get_site_registry()
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

def remove_asset(item, registry=None, catalog=None, name=None, event=True):
	if event:
		notify(WillRemovePresentationAssetEvent(item))
	# remove utility
	name = item.ntiid or name
	provided = iface_of_asset(item)
	registry = get_registry_4_item(item, provided, name, registry=registry)
	if name and not unregisterUtility(registry, provided=provided, name=name):
		logger.warn("Could not unregister %s,%s from %s",
					provided.__name__, name, registry.__parent__)
	# unindex
	catalog = get_library_catalog() if catalog is None else catalog
	catalog.unindex(item)
	# broadcast removed
	notify_removed(item)  # remove intid

def remove_mediaroll(item, registry=None, catalog=None, name=None, event=True):
	if isinstance(item, six.string_types):
		item = component.queryUtility(INTIMediaRoll, name=item)
	if item is None:
		return
	name = item.ntiid or name
	registry = get_registry_4_item(item, INTIMediaRoll, name, registry=registry)
	catalog = get_library_catalog() if catalog is None else catalog
	# remove mediarefs first
	for media in tuple(item):  # mutating
		remove_asset(media, registry, catalog, event=event)
	# remove roll
	remove_asset(item, registry, catalog, name=name, event=event)

def remove_group(group, registry=None, catalog=None, package=False,
				 name=None, event=True):
	if isinstance(group, six.string_types):
		group = component.queryUtility(INTICourseOverviewGroup, name=group)
	if group is None:
		return
	name = group.ntiid or name
	registry = get_registry_4_item(group, INTICourseOverviewGroup, name, registry=registry)
	catalog = get_library_catalog() if catalog is None else catalog
	# remove items first
	for item in tuple(group):  # mutating
		provided = iface_of_asset(item)
		if INTIMediaRoll.providedBy(item):
			remove_mediaroll(item, registry, catalog, event=event)
		elif package or provided not in PACKAGE_CONTAINER_INTERFACES:
			remove_asset(item, registry, catalog, event=event)
	# remove groups
	remove_asset(group, registry, catalog, name=name, event=event)

def remove_lesson(item, registry=None, catalog=None, package=False,
				  name=None, event=True):
	if isinstance(item, six.string_types):
		item = component.queryUtility(INTILessonOverview, name=item)
	if item is None:
		return
	name = item.ntiid or name
	registry = get_registry_4_item(item, INTILessonOverview, name, registry=registry)
	catalog = get_library_catalog() if catalog is None else catalog
	# remove groups first
	for group in tuple(item):  # mutating
		remove_group(group, registry, catalog, package=package, event=event)
	# remove asset
	remove_asset(item, registry, catalog, name=name, event=event)

def remove_presentation_asset(item, registry=None, catalog=None,
							  package=False, name=None, event=True):
	if INTILessonOverview.providedBy(item):
		remove_lesson(item, registry, catalog, package=package, name=name, event=event)
	elif INTICourseOverviewGroup.providedBy(item):
		remove_group(item, registry, catalog, package=package, name=name, event=event)
	elif INTIMediaRoll.providedBy(item):
		remove_mediaroll(item, registry, catalog, name=name, event=event)
	else:
		remove_asset(item, registry, catalog, name=name, event=event)

def make_asset_ntiid(nttype, creator=SYSTEM_USER_NAME, base=None, extra=None, now=None):
	if type(nttype) == InterfaceClass:
		nttype = nttype.__name__[1:]

	now = time.time() if now is None else now
	current_time = time_to_64bit_int(now)
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
	return find_interface(node, ICourseInstance, strict=False)
course_for_node = get_course_for_node

def create_lesson_4_node(node, ntiid=None, registry=None, catalog=None, sites=None):
	creator = getattr(node, 'creator', None)
	creator = getattr(creator, 'username', creator)
	if not ntiid:
		extra = generate_random_hex_string(6).upper()
		ntiid = make_asset_ntiid(nttype=INTILessonOverview,
								 base=node.ntiid,
								 extra=extra)

	result = NTILessonOverView()
	result.__parent__ = node  # lineage
	result.ntiid = ntiid
	result.creator = creator
	result.title = getattr(node, 'title', None)

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
		# add to course container
		course = get_course_for_node(node)
		if course is not None:
			entry = ICourseCatalogEntry(course)
			container = IPresentationAssetContainer(course)
			ntiids = (entry.ntiid,)  # container ntiid
			container[ntiid] = result  # add to container
		else:
			ntiids = None

		# register lesson
		intid_register(result, registry=registry, event=False)
		registerUtility(registry,
						result,
						provided=INTILessonOverview,
						name=ntiid)

		# XXX: set the src field to be unique for indexing see MediaByOutlineNode
		if not getattr(node, 'src', None):
			oid = to_external_ntiid_oid(result)
			node.src = safe_filename(oid) + '.json'  # make it a json file

		# index
		catalog = get_library_catalog() if catalog is None else catalog
		catalog.index(result, container_ntiids=ntiids,
					  namespace=node.src, sites=sites)

	# lesson is ready
	return result

def check_docket_targets(asset):
	if INTIDocketAsset.providedBy(asset) and not asset.target:
		href = asset.href
		if IPloneNamed.providedBy(href):
			asset.target = to_external_ntiid_oid(href)
			asset_type = getattr(href, 'contentType', None) or asset.type
			asset.type = to_unicode(asset_type) if asset_type else None
		elif is_valid_ntiid_string(href):
			asset.target = href
		elif is_internal_file_link(href):
			ext = get_file_from_external_link(href)
			asset.target = to_external_ntiid_oid(ext)
			asset_type = getattr(ext, 'contentType', None) or asset.type
			asset.type = to_unicode(asset_type) if asset_type else None
		return True
	return False
check_related_work_target = check_docket_targets # BWC
