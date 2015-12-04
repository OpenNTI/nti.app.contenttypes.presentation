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

from zope.intid import IIntIds

from zope.location.location import locate
from zope.location.interfaces import ILocation

from zope.traversing.interfaces import IEtcNamespace

from ZODB.interfaces import IConnection

from nti.common.time import time_to_64bit_int
from nti.common.random import generate_random_hex_string

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation.lesson import NTILessonOverView
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import WillRemovePresentationAssetEvent

from nti.externalization.oids import to_external_ntiid_oid

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility
from nti.site.site import get_component_hierarchy_names

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
			intids = component.getUtility(IIntIds)
			intids.register(item, event=False)
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

def catalog_entry_for_node(node):
	course = find_interface(node, ICourseInstance, strict=False)
	entry = ICourseCatalogEntry(course, None)
	return entry

def create_lesson_4_node(node, ntiid=None, registry=None, catalog=None):
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

	# XXX: set src and lesson ntiid (see MediaByOutlineView)
	# at his point is very likely that LessonOverviewNTIID,
	# ContentNTIID are simply alias fields. All of them
	# are kept so long as we have manual sync and BWC
	node.LessonOverviewNTIID = ntiid

	# XXX: if registry is specified register the new node
	if registry is not None:
		# register lesson
		registry = get_registry(registry)
		intid_register(result, registry=registry, event=False)
		registerUtility(registry,
						result,
						provided=INTILessonOverview,
						name=ntiid)

		# XXX: set the src field to be unique for indexing see MediaByOutlineNode
		if not getattr(node, 'src', None):
			node.src = to_external_ntiid_oid(result)

		# XXX index lesson
		catalog = get_library_catalog() if catalog is None else catalog
		entry = catalog_entry_for_node(node)
		ntiids = (entry.ntiid,) if entry is not None else None
		catalog.index(result, container_ntiids=ntiids, namespace=node.src)

	# lesson is ready
	return result