import codecs
from setuptools import setup, find_packages

VERSION = '0.0.0'

entry_points = {
	"z3c.autoinclude.plugin": [
		'target = nti.app',
	],
	'console_scripts': [
		"nti_remove_invalid_assets = nti.app.contenttypes.presentation.scripts.nti_remove_invalid_assets:main",
		"nti_sync_lessons_overviews = nti.app.contenttypes.presentation.scripts.nti_sync_lessons_overviews:main",
	],
}

setup(
	name='nti.app.contenttypes.presentation',
	version=VERSION,
	author='Jason Madden',
	author_email='jason@nextthought.com',
	description="NTI Application Presentation Content Types",
	long_description=codecs.open('README.rst', encoding='utf-8').read(),
	license='Proprietary',
	keywords='Content Presentation',
	classifiers=[
		'Intended Audience :: Developers',
		'Natural Language :: English',
		'Operating System :: OS Independent',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: Implementation :: CPython'
	],
	packages=find_packages('src'),
	package_dir={'': 'src'},
	namespace_packages=['nti', 'nti.app', 'nti.app.contenttypes'],
	install_requires=[
		'setuptools'
	],
	entry_points=entry_points
)
