#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 6

from zope.component.hooks import setHooks

from nti.contentlibrary.indexed_data.interfaces import IContainedObjectCatalog
from nti.contentlibrary.indexed_data import CATALOG_INDEX_NAME as  LIB_INDEX_NAME

from .. import CATALOG_INDEX_NAME as PA_INDEX_NAME

from ..interfaces import IPresentationAssetsIndex

def do_evolve(context):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']
	from IPython.core.debugger import Tracer; Tracer()()
	lsm = dataserver_folder.getSiteManager()
	pa_catalog = lsm.getUtility(IPresentationAssetsIndex, name=PA_INDEX_NAME)
	lib_catalog = lsm.getUtility(IContainedObjectCatalog, name=LIB_INDEX_NAME)

	# move data
	for name in ('_type_index', '_namespace_index'):
		src_index = getattr(pa_catalog, name)
		tgt_index = getattr(lib_catalog, name)
		for doc_id, value in src_index.documents_to_values.items():
			tgt_index.index_doc(doc_id, value)

	src_index = pa_catalog._entry_index
	tgt_index = lib_catalog._container_index
	for doc_id, value in src_index.documents_to_values.items():
		tgt_index.index_doc(doc_id, value)

	# remove old indexes
	for name in ('_type_index', '_entry_index', '_namespace_index'):
		if hasattr(pa_catalog, name):
			delattr(pa_catalog, name)

def evolve(context):
	"""
	Evolve to generation 6 by removing unused catalog indices
	"""
	do_evolve(context)
