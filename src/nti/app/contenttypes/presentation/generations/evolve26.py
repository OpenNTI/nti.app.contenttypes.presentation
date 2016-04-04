#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 25

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.intid.common import addIntId

from nti.site.hostpolicy import get_all_host_sites

from nti.site.utils import registerUtility

@interface.implementer(IDataserver)
class MockDataserver(object):

	root = None

	def get_by_oid(self, oid, ignore_creator=False):
		resolver = component.queryUtility(IOIDResolver)
		if resolver is None:
			logger.warn("Using dataserver without a proper ISiteManager configuration.")
		else:
			return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
		return None

def _update_refs(current_site, catalog, intids, seen):
	registry = current_site.getSiteManager()
	for name, group in list(component.getUtilitiesFor(INTICourseOverviewGroup)):
		if name in seen:
			continue
		seen.add(name)

		for idx, item in enumerate(group or ()):  # mutating
			reference = None

			if INTITimeline.providedBy(item):
				reference = INTITimelineRef(item)
			elif INTISlideDeck.providedBy(item):
				reference = INTISlideDeckRef(item)

			if reference is not None:
				reference.__parent__ = group
				addIntId(reference)
				registerUtility(registry,
								reference,
								iface_of_asset(reference),
								name=reference.ntiid)

				namespace = catalog.get_namespace(group)

				# remove containers from hard item
				ntiids = (group.ntiid, group.__parent__.ntiid)
				catalog.update_containers(item, ntiids)

				containers = set(catalog.get_containers(group) or ())
				containers.update(ntiids)

				catalog.index(reference,
							  namespace=namespace,
							  container_ntiids=containers,
							  sites=(current_site.__name__,),
							  intids=intids)

				group[idx] = reference


def do_evolve(context, generation=generation):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = dataserver_folder
	component.provideUtility(mock_ds, IDataserver)

	with site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = dataserver_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)

		seen = set()
		catalog = get_library_catalog()

		for current_site in get_all_host_sites():
			with site(current_site):
				_update_refs(current_site, catalog, intids, seen)
		logger.info('Dataserver evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to 26 by moving timeline and slidedeck to refs objects inside groups
	"""
	do_evolve(context, generation)
