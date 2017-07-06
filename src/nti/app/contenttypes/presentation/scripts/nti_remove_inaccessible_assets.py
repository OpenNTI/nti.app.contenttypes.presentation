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

from nti.app.contenttypes.presentation.utils.common import remove_all_inaccessible_assets

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver.utils import run_with_dataserver

from nti.dataserver.utils.base_script import create_context


def _load_library():
    library = component.queryUtility(IContentPackageLibrary)
    if library is not None:
        library.syncContentPackages()


def _process_args(args):
    _load_library()
    result = remove_all_inaccessible_assets()
    if args.verbose:
        print()
        pprint.pprint(result)
        print()


def main():
    arg_parser = argparse.ArgumentParser(description="Remove inaccessible assets")
    arg_parser.add_argument('-v', '--verbose', help="Be Verbose",
                            action='store_true', dest='verbose')

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
