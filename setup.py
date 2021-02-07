from setuptools import setup, find_packages
from postcard_creator import __version__

reqs = [
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
    autor_email='hi@abertschi.ch',
    # install_requires=reqs,
    description='A python wrapper around the Rest API of the Swiss Postcard creator',
    packages=find_packages(where='postcard_creator'),
    package_dir={
        '': 'postcard_creator',
    },
    platforms='any',
    keywords='postcard creator swiss',
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        # 'Programming Language :: Python :: 3.3',
        # 'Programming Language :: Python :: 3.4',
        # 'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    setup_requires=['pytest-runner'],
    package_data={'postcard_creator': ['page_1.svg', 'page_2.svg', 'open_sans_emoji.ttf']},
    test_suite = 'tests',
    # extras_require={
    #     ':python_version=="3.2"': ['virtualenv<14', 'pytest<3'],
    # }
)
