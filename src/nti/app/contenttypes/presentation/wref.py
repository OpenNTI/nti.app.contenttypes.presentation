#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Weak-references to presentation asset objects. Like all weak references,
these are meant to be pickled with no external dependencies,
and when called, to be able to look up what they are missing.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.app.contenttypes.presentation import iface_of_thing

from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import IGroupOverViewableWeakRef

@component.adapter(IGroupOverViewable)
@interface.implementer(IGroupOverViewableWeakRef)
class GroupOverViewableWeakRef(object): 

	def __init__(self, asset):
		self._name = asset.ntiid
		self._provided = iface_of_thing(asset)

	def __getstate__(self):
		return (1,
				self._name,
				self._provided)

	def __setstate__(self, state):
		assert isinstance(state, tuple)
		assert state[0] == 1
		self._name = state[1]
		self._provided = state[2]

	def __str__(self):
		return "GroupOverViewableWeakRef(%s, %s)" % (self._provided, self._name)
	
	def __eq__(self, other):
		try:
			return other is self or self.__getstate__() == other.__getstate__()
		except AttributeError:
			return NotImplemented

	def __hash__(self):
		return hash(self.__getstate__())

	def __call__(self):
		result = component.queryUtility(self._provided, name=self._name)
		return result
