#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import sys
import argparse

from zope import component

from zope.interface.adapter import _lookupAll as zopeLookupAll

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.utils import run_with_dataserver
from nti.dataserver.utils.base_script import create_context

from nti.intid.common import removeIntId

from nti.site.hostpolicy import get_all_host_sites

from nti.site.utils import unregisterUtility

def _lookupAll(main):
	result = {}
	required = ()
	order = len(required)
	for registry in main.utilities.ro: # must keep order
		byorder = registry._adapters
		if order >= len(byorder):
			continue
		components = byorder[order]
		extendors = ALL_PRESENTATION_ASSETS_INTERFACES
		zopeLookupAll(components, required, extendors, result, 0, order)  
		break # break on first
	return result

def _process_items(current, intids, catalog, seen):
	site_name = current.__name__
	registry = current.getSiteManager()
	site_components = _lookupAll(registry)
	logger.warn("%s(s) asset(s) found in %s, %s", len(site_components), site_name)

	for ntiid, item in site_components.items():
		provided = iface_of_asset(item)
		doc_id = intids.queryId(item)

		# registration for a removed asset
		if doc_id is None:
			logger.warn("Removing invalid registration %s from site %s",
						ntiid, site_name)
			unregisterUtility(registry, item, provided=provided, name=ntiid, force=True)
			continue

		# invalid lesson overview
		if INTILessonOverview.providedBy(item) and item.__parent__ is None:
			logger.warn("Removing invalid lesson overview %s from site %s",
						ntiid, site_name)
			removeIntId(item)
			catalog.unindex_doc(doc_id)
			unregisterUtility(registry, provided=provided, name=ntiid)
			continue

		# registration not in base site
		if ntiid in seen:
			logger.warn("Removing %s from site %s", ntiid, site_name)
			unregisterUtility(registry, provided=provided, name=ntiid)

		seen.add(ntiid)

def _process_args(args):
	seen = set()
	catalog = get_library_catalog()
	intids = component.getUtility(IIntIds)
	for current in get_all_host_sites():
		_process_items(current, intids, catalog, seen)

def main():
	arg_parser = argparse.ArgumentParser(description="Remove invalid presentation assets")
	arg_parser.add_argument('-v', '--verbose', help="Be Verbose", action='store_true',
							dest='verbose')

	args = arg_parser.parse_args()
	env_dir = os.getenv('DATASERVER_DIR')
	if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
		raise IOError("Invalid dataserver environment root directory")

	conf_packages = ('nti.appserver',)
	context = create_context(env_dir, with_library=True)

	run_with_dataserver(environment_dir=env_dir,
						verbose=args.verbose,
						xmlconfig_packages=conf_packages,
						context=context,
						minimal_ds=True,
						function=lambda: _process_args(args))
	sys.exit(0)

if __name__ == '__main__':
	main()
