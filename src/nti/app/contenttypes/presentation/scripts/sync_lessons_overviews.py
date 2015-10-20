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

from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.utils import run_with_dataserver
from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from ..utils.common import yield_sync_courses as yield_courses

from ..subscribers import get_course_packages
from ..subscribers import synchronize_course_lesson_overview

def _sync_course(course, exclude=False, force=False):
	result = []
	result.extend(synchronize_course_lesson_overview(course, force=force))
	if not exclude and not ICourseSubInstance.providedBy(course):
		for sub_instance in (course.SubInstances or {}).values():
			result.extend(synchronize_course_lesson_overview(sub_instance))
	return result

def _sync_courses(args):
	result = []
	for course in yield_courses(args.list, args.ntiids):
		result.extend(_sync_course(course, args.exclude, args.force))
	return result

def _process_args(args):
	set_site(args.site)

	if not args.list:
		_sync_courses(args)
	else:
		print()
		for course in yield_courses(all_courses=True):
			if ICourseSubInstance.providedBy(course):
				continue
			entry = ICourseCatalogEntry(course)
			print("==>", entry.ntiid)
			for content_package in get_course_packages(course):
				print('\t', content_package.ntiid)
		print()

def main():
	arg_parser = argparse.ArgumentParser(description="Course lessons overviews synchronizer")
	arg_parser.add_argument('-v', '--verbose', help="Be Verbose", action='store_true',
							dest='verbose')

	arg_parser.add_argument('-x', '--exclude', help="Exclude course sub-instances",
							action='store_true', dest='exclude')

	arg_parser.add_argument('-f', '--force', help="Force update",
							action='store_true', dest='force')
	
	arg_parser.add_argument('-s', '--site',
							dest='site',
							help="Application SITE.")

	site_group = arg_parser.add_mutually_exclusive_group()
	site_group.add_argument('-n', '--ntiids',
							 dest='ntiids',
							 nargs="+",
							 default=(),
							 help="The courses [entries] NTIIDs")

	site_group.add_argument('--all',
							 dest='all',
							 action='store_true',
							 help="All courses")

	site_group.add_argument('--list',
							 dest='list',
							 action='store_true',
							 help="List sync courses")

	args = arg_parser.parse_args()
	env_dir = os.getenv('DATASERVER_DIR')
	if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
		raise IOError("Invalid dataserver environment root directory")

	if not args.site:
		raise ValueError("Application site not specified")

	conf_packages = ('nti.appserver',)
	context = create_context(env_dir, with_library=True)

	run_with_dataserver(environment_dir=env_dir,
						verbose=args.verbose,
						xmlconfig_packages=conf_packages,
						context=context,
						minimal_ds=True,
						function=lambda: _process_args(args))
	sys.exit(0)

if __name__ == '__main__':
	main()
