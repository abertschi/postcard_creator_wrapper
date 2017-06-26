from setuptools import setup, find_packages
from pip.req import parse_requirements
import codecs
import os
import sys
import re

here = os.path.abspath(os.path.dirname(__file__))
install_reqs = parse_requirements('./requirements.txt', session='hack')
reqs = [str(ir.req) for ir in install_reqs]


def read(*parts):
    # intentionally *not* adding an encoding option to open
    return codecs.open(os.path.join(here, *parts), 'r').read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name='postcard_creator',
    version=find_version('postcard_creator', '__init__.py'),
    url='http://github.com/abertschi/postcard_creator_wrapper',
    license='Apache Software License',
    author='Andrin Bertschi',
    install_requires=reqs,
    description='A python wrapper around the Rest API of the Swiss Postcard creator',
    packages=['postcard_creator'],
    platforms='any',
    keywords='postcard creator swiss',
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',

        'Programming Language :: Python :: 3.6',
    ],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    package_data={'postcard_creator': ['page_1.svg', 'page_2.svg']},
    extras_require={
        'test': ['coverage', 'pytest'],
    }
)
