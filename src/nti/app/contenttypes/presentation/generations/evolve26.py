#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 26

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from nti.app.contenttypes.presentation.utils import registry_by_name

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.coremetadata.interfaces import IRecordable

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import get_all_host_sites

from nti.site.interfaces import IHostPolicyFolder

from nti.site.utils import registerUtility

from nti.traversal.traversal import find_interface

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

def _is_obj_locked(obj):
	return IRecordable.providedBy(obj) and obj.isLocked()

def _fix_related_work_ref_target(current_site, work_ref):
	# Only need authored objects with ntiid hrefs.
	if 		_is_obj_locked(work_ref) \
		and is_valid_ntiid_string(work_ref.href):

		href_obj = find_object_with_ntiid(work_ref.href)
		# Only pointing to content units
		if href_obj is not None and IContentUnit.providedBy(href_obj):
			logger.info('[%s] NTIRelatedWorkRef target fixed (ntiid=%s) (old=%s) (new=%s)',
						 current_site.__name__,
						 work_ref.ntiid,
						 work_ref.target, work_ref.href)
			work_ref.target = work_ref.href

def _get_site_name(group):
	folder = find_interface(group, IHostPolicyFolder, strict=False)
	return folder.__name__ if folder is not None else None

def _get_host_registry(group):
	return registry_by_name(_get_site_name(group))

def _update_assets(seen, current_site):
	library = component.queryUtility(IContentPackageLibrary)
	if library is None:
		return

	# Loop through all assets in all groups.
	for name, group in list(component.getUtilitiesFor(INTICourseOverviewGroup)):
		if name in seen:
			continue
		seen.add(name)
		if not group:
			continue
		for item in group:
			asset_interface = iface_of_asset(item)
			registered = component.queryUtility(asset_interface, name=item.ntiid)
			if registered is None:
				host_registry = _get_host_registry(group)
				# Some dev machines have weird state.
				if item.ntiid and host_registry is not None:
					registerUtility(host_registry,
									provided=asset_interface,
									component=item,
									name=item.ntiid)
					logger.info('[%s] Asset registered (ntiid=%s) (site=%s)',
							 	current_site.__name__,
								item.ntiid,
								_get_site_name(group))
				else:
					logger.info('No ntiid/registry for (%s) (%s)', item, host_registry)

			if INTIRelatedWorkRef.providedBy(item):
				_fix_related_work_ref_target(current_site, item)

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

		# Load library
		library = component.queryUtility(IContentPackageLibrary)
		if library is not None:
			library.syncContentPackages()

		seen = set()
		# Do not need to do this in global site.
		for current_site in get_all_host_sites():
			with site(current_site):
				_update_assets(seen, current_site)
		logger.info('Dataserver evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to 26 by making sure assets are registered and related work refs
	have proper targets.
	"""
	do_evolve(context, generation)
