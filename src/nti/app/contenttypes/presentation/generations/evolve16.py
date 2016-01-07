#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 16

from zope import component

from zope.component.hooks import site
from zope.component.hooks import site as current_site

from persistent.list import PersistentList

from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.site.hostpolicy import get_all_host_sites

def _process_groups(registry):
	count = 0
	for _, group in list(registry.getUtilitiesFor(INTICourseOverviewGroup)):
		for item in group:
			if INTITimeline.providedBy(item) or INTIRelatedWorkRef.providedBy(item):
				continue
			if item.__parent__ is None:
				item.__parent__ = group
		count += 1
	return count

def _process_rolls(registry):
	count = 0
	for _, roll in list(registry.getUtilitiesFor(INTIMediaRoll)):
		for item in roll:
			if item.__parent__ is None:
				item.__parent__ = roll
		items = roll.Items
		if items and not isinstance(object, PersistentList):
			roll.Items = PersistentList(items)
		count += 1
	return count

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		for site in get_all_host_sites():
			with current_site(site):
				registry = component.getSiteManager()
				_process_groups(registry)
				_process_rolls(registry)

	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 16 by setting lineage group items and media roll items
	"""
	do_evolve(context, generation)
