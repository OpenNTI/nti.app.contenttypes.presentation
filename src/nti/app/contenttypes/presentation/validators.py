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

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIAudioRef
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef

from .interfaces import IItemRefValidator

@interface.implementer(IItemRefValidator)
class _ItemRefValidator(object):
	
	provided = None
	item_type = None
	field_name = None
	
	def __init__(self, item):
		self.item = item

	def validate(self): 
		name = getattr(self.item, self.field_name, None) or u''
		reference = component.queryUtility(self.provided, name=name)
		if reference is None:
			logger.error("Could not find %s %s", self.item_type, name)
		return bool(reference is None)
	
@component.adapter(INTIAssignmentRef)
class _AssignmentRefValidator(_ItemRefValidator):
	field_name = 'target'
	item_type = 'Assignment'
	provided = IQAssignment
	
@component.adapter(INTIVideoRef)
class _VideoRefValidator(_ItemRefValidator):	
	field_name = 'ntiid'
	item_type = 'Video'
	provided = INTIVideo
	
@component.adapter(INTIAudioRef)
class _AudioRefValidator(_ItemRefValidator):	
	field_name = 'ntiid'
	item_type = 'Audio'
	provided = INTIAudio

	