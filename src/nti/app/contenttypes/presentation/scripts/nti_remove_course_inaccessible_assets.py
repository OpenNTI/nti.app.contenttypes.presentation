#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import sys
import pprint
import argparse

from zope import component

from zope.component.hooks import site as current_site

from nti.app.contenttypes.presentation.utils.common import remove_course_inaccessible_assets

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver.utils import run_with_dataserver

from nti.dataserver.utils.base_script import create_context

from nti.site.hostpolicy import get_host_site
from nti.site.hostpolicy import get_all_host_sites

def _load_library():
    library = component.queryUtility(IContentPackageLibrary)
    if library is not None:
        library.syncContentPackages()


def _process_args(args):
    _load_library()
    if args.verbose:
        print()
    if args.all:
        sites = get_all_host_sites()
    else:
        sites = map(get_host_site, args.sites or ())
    for site in sites:
        with current_site(site):
            result = remove_course_inaccessible_assets()
            if args.verbose:
                pprint.pprint(result)
                print()


def main():
    arg_parser = argparse.ArgumentParser(description="Remove course inaccessible assets")
    arg_parser.add_argument('-v', '--verbose', help="Be Verbose", 
                            action='store_true', dest='verbose')

    site_group = arg_parser.add_mutually_exclusive_group()
    site_group.add_argument('-s', '--sites', nargs="+",
                            dest='sites',
                            help="Application site(s).")

    site_group.add_argument('--all',
                            dest='all',
                            action='store_true',
                            help="All sites")

    args = arg_parser.parse_args()

    env_dir = os.getenv('DATASERVER_DIR')
    if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
        raise IOError("Invalid dataserver environment root directory")

    conf_packages = ('nti.appserver',)
    context = create_context(env_dir, with_library=True)

    run_with_dataserver(environment_dir=env_dir,
                        verbose=args.verbose,
                        context=context,
                        minimal_ds=True,
                        xmlconfig_packages=conf_packages,
                        function=lambda: _process_args(args))
    sys.exit(0)


if __name__ == '__main__':
    main()
