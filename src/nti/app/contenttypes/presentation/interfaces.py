#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import interface

from zope.deprecation import deprecated

deprecated('IPresentationAssetsIndex', 'Use lastest library implementation')
class IPresentationAssetsIndex(interface.Interface):
	pass

class IItemRefValidator(interface.Interface):

	def validate():
		"""
		Return whether or not the item reference is valid
		"""

class ILessonPublicationPredicate(interface.Interface):

	def is_satisfied(self, constraint):
		"""
		Return whether or not a constraint is satisfied.
		"""

class IAssignmentCompletionPredicate(ILessonPublicationPredicate):

	def is_satisfied(self, constraint):
		"""
		Evaluates an assignment completion constraint. Returns true
		if all assignments are either completed or closed; false otherwise.
		"""
