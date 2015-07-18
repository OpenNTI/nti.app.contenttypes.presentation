#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 10

from .evolve9 import do_evolve

def evolve(context):
	"""
	Evolve to gen 10 by registering assets with course
	"""
	do_evolve(context, generation)
