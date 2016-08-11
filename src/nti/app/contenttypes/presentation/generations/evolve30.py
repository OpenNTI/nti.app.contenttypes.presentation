#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 30

from nti.app.contenttypes.presentation.generations import evolve27

def evolve(context):
	"""
	Evolve to 30 by converting all timeline objects in groups to timeline refs.
	"""
	evolve27.do_evolve(context, generation)
