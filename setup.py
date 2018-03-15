import codecs
from setuptools import setup, find_packages

entry_points = {
    "z3c.autoinclude.plugin": [
        'target = nti.app',
    ],
}


TESTS_REQUIRE = [
    'nti.app.testing',
    'nti.testing',
    'zope.dottedname',
    'zope.testrunner',
]


def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='nti.app.contenttypes.presentation',
    version=_read('version.txt').strip(),
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="Application-level content presentation",
    long_description=(_read('README.rst') + '\n\n' + _read("CHANGES.rst")),
    license='Apache',
    keywords='pyramid content presentation',
    classifiers=[
        'Framework :: Zope',
        'Framework :: Pyramid',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    url="https://github.com/NextThought/nti.app.contenttypes.presentation",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.app', 'nti.app.contenttypes'],
    tests_require=TESTS_REQUIRE,
    install_requires=[
        'setuptools',
        'nti.app.assessment',
        'nti.app.products.courseware',
        'nti.app.contenttypes.completion',
        'nti.assessment',
        'nti.base',
        'nti.common',
        'nti.contentindexing',
        'nti.contentlibrary',
        'nti.contenttypes.courses',
        'nti.contenttypes.presentation',
        'nti.coremetadata',
        'nti.externalization',
        'nti.links',
        'nti.mimetype',
        'nti.namedfile',
        'nti.ntiids',
        'nti.publishing',
        'nti.recorder',
        'nti.schema',
        'nti.site',
        'nti.traversal',
        'nti.zodb',
        'pyramid',
        'requests',
        'simplejson',
        'six',
        'transaction',
        'zc.intid',
        'ZODB',
        'zope.cachedescriptors',
        'zope.component',
        'zope.event',
        'zope.generations',
        'zope.i18n',
        'zope.interface',
        'zope.intid',
        'zope.lifecycleevent',
        'zope.location',
        'zope.security',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
        'docs': [
            'Sphinx',
            'repoze.sphinx.autointerface',
            'sphinx_rtd_theme',
        ],
    },
    entry_points=entry_points,
)
