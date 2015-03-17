#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import sys
import argparse

from zope import component

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.utils import run_with_dataserver
from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from nti.ntiids.ntiids import find_object_with_ntiid
    
from ..subscribers import get_course_packages
from ..subscribers import synchronize_content_package
from ..subscribers import synchronize_course_lesson_overview

def _process_args(args):
    set_site(args.site)

    ntiid = args.ntiid
    obj = find_object_with_ntiid(ntiid)
    course_instance = ICourseInstance(obj, None)
    if course_instance is None:
        try:
            catalog = component.getUtility(ICourseCatalog)
            catalog_entry = catalog.getCatalogEntry(ntiid)
            course_instance = ICourseInstance(catalog_entry, None)
        except KeyError:
            course_instance = None

    if course_instance is None:
        raise ValueError("Course not found")
    
    result = []
    for content_package in get_course_packages(course_instance):
        items = synchronize_content_package(content_package)
        result.extend(items or ())
    
    items = synchronize_course_lesson_overview(course_instance)
    result.extend(items or ())
    
    return result
    
def main():
    arg_parser = argparse.ArgumentParser(description="Course lessons overviews synchronizer")
    arg_parser.add_argument('-v', '--verbose', help="Be Verbose", action='store_true',
                            dest='verbose')
    arg_parser.add_argument( 'ntiid', help="The course [entry] NTIID" )
    arg_parser.add_argument('--site',
                            dest='site',
                            help="Application SITE.")
    
    args = arg_parser.parse_args()
    env_dir = os.getenv('DATASERVER_DIR')
    if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
        raise IOError("Invalid dataserver environment root directory")
    
    conf_packages = ('nti.appserver',)
    context = create_context(env_dir, with_library=True)

    run_with_dataserver(environment_dir=env_dir,
                        xmlconfig_packages=conf_packages,
                        context=context,
                        minimal_ds=True,
                        function=lambda: _process_args(args))
    sys.exit(0)

if __name__ == '__main__':
    main()
