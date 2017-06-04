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
    name='postcard_creator_wrapper',
    version=find_version('postcard_creator_wrapper', '__init__.py'),
    url='http://github.com/abertschi/postcard_creator_wrapper',
    license='Apache Software License',
    author='Andrin Bertschi',
    install_requires=reqs,
    description='A wrapper around the postcard creator API of swiss post',
    packages=['postcard_creator_wrapper'],
    include_package_data=True,
    platforms='any',
    classifiers=[
        ],
    extras_require={
      }
)