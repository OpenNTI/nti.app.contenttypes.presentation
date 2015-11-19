#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 13

import functools

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.coremetadata.interfaces import IDefaultPublished

from nti.site.hostpolicy import run_job_in_all_host_sites

def _remove_interface():
	for _, item in list(component.getUtilitiesFor(IPresentationAsset)):
		interface.noLongerProvides(item, IDefaultPublished)
			
def do_evolve(context, generation=generation):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	with site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		run_job_in_all_host_sites(functools.partial(_remove_interface))
		logger.info('Evolution %s done.', generation)
		
def evolve(context):
	"""
	Evolve to gen 13 by removing interface from assets
	"""
	do_evolve(context)
