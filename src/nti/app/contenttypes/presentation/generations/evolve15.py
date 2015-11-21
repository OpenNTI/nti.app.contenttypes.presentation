#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 15

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import site as current_site

from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.interfaces import ICalendarPublishable

from nti.site.hostpolicy import get_all_host_sites

def _process_lessons( registry ):
	count = 0
	for _, obj in list(registry.getUtilitiesFor(INTILessonOverview)):
		interface.alsoProvides( obj, ICalendarPublishable )
		count += 1
	return count

def _process_nodes( registry ):
	count = 0
	for _, obj in list(registry.getUtilitiesFor(ICourseOutlineNode)):
		interface.alsoProvides( obj, ICalendarPublishable )
		count += 1
	return count

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	node_count = lesson_count = 0
	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		for site in get_all_host_sites():
			with current_site(site):
				registry = component.getSiteManager()
				node_count += _process_nodes( registry )
				lesson_count += _process_lessons( registry )

	logger.info('Evolution %s done (nodes=%s) (lessons=%s).',
				generation, node_count, lesson_count )

def evolve(context):
	"""
	Evolve to generation 15 by marking outline nodes and lessons
	ICalendarPublishable.
	"""
	do_evolve(context, generation)
