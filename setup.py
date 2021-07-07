from setuptools import setup, find_packages
from postcard_creator import __version__

# XXX: Ensure that all dependencies are added here when releasing new version
dependencies = [
    'beautifulsoup4',
    'Pillow',
    'requests-toolbelt',
    'cookies',
    'idna',
    'requests',
    'urllib3',
    'python_resize_image',
    'colorthief'
]

setup(
    name='postcard_creator',
    version=__version__,
    url='http://github.com/abertschi/postcard_creator_wrapper',
    license='Apache Software License',
    author='Andrin Bertschi',
    author_email='apps@abertschi.ch',
    packages=['postcard_creator'],
    include_package_data=True,
    install_requires=dependencies,
    description='A python wrapper around the Rest API of the Swiss Postcard creator',
    platforms='any',
    keywords='postcard creator swiss',
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    package_data={'postcard_creator': ['page_1.svg', 'page_2.svg', 'open_sans_emoji.ttf', 'OpenSans-Regular.ttf']},
)
