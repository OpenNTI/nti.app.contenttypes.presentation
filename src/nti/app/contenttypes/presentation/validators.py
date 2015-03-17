#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.assessment.interfaces import IQAssignment

from nti.contenttypes.presentation.interfaces import INTIAssignmentRef

from .interfaces import IItemRefValidator

@component.adapter(INTIAssignmentRef)
@interface.implementer(IItemRefValidator)
class _AssignmentRefValidator(object):
	
	def __init__(self, item):
		self.item = item

	def validate(self): 
		target = self.item.target
		assignment = component.queryUtility(IQAssignment, name=target)
		if assignment is None:
			logger.error("Could not find assignment %s", target)
		return bool(assignment is None)
