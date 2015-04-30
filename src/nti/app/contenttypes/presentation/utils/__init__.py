#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE

from nti.contenttypes.presentation.interfaces import PUBLIC
from nti.contenttypes.presentation.interfaces import CREDIT
from nti.contenttypes.presentation.interfaces import EVERYONE
from nti.contenttypes.presentation.interfaces import PURCHASED

from .registry import remove_utilities

VISIBILITY_SCOPE_MAP = {
	ES_ALL: EVERYONE,
	ES_PUBLIC: PUBLIC,
	ES_CREDIT: CREDIT,
	ES_PURCHASED: PURCHASED,
	ES_CREDIT_DEGREE: CREDIT,
	ES_CREDIT_NONDEGREE: CREDIT,
}

def get_visibility_for_scope(scope):
	return VISIBILITY_SCOPE_MAP.get(scope)
