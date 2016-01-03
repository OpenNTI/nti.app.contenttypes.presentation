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

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.contentlibrary.utils import yield_content_packages
from nti.app.contentlibrary.subscribers import update_indices_when_content_changes

from nti.contentlibrary.indexed_data import get_library_catalog
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver.utils import run_with_dataserver
from nti.dataserver.utils.base_script import create_context

from nti.intid.common import removeIntId

from nti.recorder.record import remove_transaction_history

from nti.site.utils import unregisterUtility
from nti.site.hostpolicy import get_all_host_sites

from ..utils.common import yield_sync_courses

from ..synchronizer import synchronize_course_lesson_overview

def remove_assets(registry, intids):
	total = 0
	logger.info('Removing assets from registry')
	for ntiid, item in list(registry.getUtilitiesFor(IPresentationAsset)):
		if intids.queryId(item) is None:
			continue
		provided = iface_of_asset(item)
		unregisterUtility(registry, provided=provided, name=ntiid)
		remove_transaction_history(item)
		removeIntId(item)
		total += 1
	logger.info('%s assets removed', total)

def remove_all_assets():
	registry = component.getSiteManager()
	intids = component.getUtility(IIntIds)
	remove_assets(registry, intids)

def _clear_package_containers(package):
	def recur(unit):
		for child in unit.children or ():
			recur(child)
		container = IPresentationAssetContainer(unit)
		container.clear()
	recur(package)

def _sync_courses():
	for course in yield_sync_courses():
		entry = ICourseCatalogEntry(course)
		logger.info("Synchronizing course %s", entry.ntiid)
		container = IPresentationAssetContainer(course)
		container.clear()
		synchronize_course_lesson_overview(course)

def _sync_pacakges():
	for pacakge in yield_content_packages():
		logger.info("Synchronizing Pacakge %s", pacakge.ntiid)
		_clear_package_containers(pacakge)
		update_indices_when_content_changes(pacakge)

def _sync_all():
	_sync_pacakges()
	_sync_courses()

def _run_job(func, msg):
	ordered = get_all_host_sites()
	for site in ordered:
		logger.info('%s %s...', msg, site.__name__)
		with current_site(site):
			func()

def _process_args(args):
	library = component.queryUtility(IContentPackageLibrary)
	if library is not None:
		library.syncContentPackages()

	logger.info("...")

	catalog = get_library_catalog()
	catalog.clear()

	_run_job(remove_all_assets, "Removing assets from")
	_run_job(_sync_all, "Processing site")

def main():
	arg_parser = argparse.ArgumentParser(description="Sync all presentation assets")
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
