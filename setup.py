from setuptools import setup
import codecs
import os
import re

here = os.path.abspath(os.path.dirname(__file__))

def read(*parts):
    return codecs.open(os.path.join(here, *parts), 'r').read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


reqs = [
    'beautifulsoup4',
    'Pillow',
    'requests-toolbelt',
    'cookies',
    'idna',
    'requests',
    'urllib3',
    'python_resize_image'
]

setup(
    name='postcard_creator',
    version='0.0.7', #find_version('postcard_creator', '__init__.py'),
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
        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    setup_requires=['pytest-runner'],
    package_data={'postcard_creator': ['page_1.svg', 'page_2.svg']}
    # extras_require={
    #     ':python_version=="3.2"': ['virtualenv<14', 'pytest<3'],
    # }
)
