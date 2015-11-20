#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 14

import functools

from zope import component

from zope.component.hooks import site
from zope.component.hooks import setHooks
	
from nti.contentlibrary.indexed_data import CATALOG_INDEX_NAME
from nti.contentlibrary.indexed_data.interfaces import IContainedObjectCatalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.site.hostpolicy import run_job_in_all_host_sites

from ..synchronizer import index_pacakge_assets

def _index_package_assets(catalog):
	course_catalog = component.queryUtility(ICourseCatalog)
	if course_catalog is not None:
		for entry in course_catalog.iterCatalogEntries():
			course = ICourseInstance(entry, None)
			if course is not None and not ILegacyCourseInstance.providedBy(course):
				index_pacakge_assets(course, catalog=catalog)
			
def do_evolve(context, generation=generation):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	with site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = dataserver_folder.getSiteManager()
		catalog = lsm.getUtility(IContainedObjectCatalog, name=CATALOG_INDEX_NAME)

		run_job_in_all_host_sites(functools.partial(_index_package_assets, catalog))
		logger.info('Evolution %s done.', generation)
		
def evolve(context):
	"""
	Evolve to gen 14 by updating containers of the package assets
	"""
	do_evolve(context)
