# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import codecs
from setuptools import setup, find_packages


tests_require = [
    'Flask-Testing>=0.4.1',
    'Flask-Principal>=0.4.0',
    'Flask-SQLAlchemy>=2.0',
    'Flask-MongoEngine>=0.7.1',
    'peewee==2.*',
    'nose>=1.1.2',
]

setup(
    name='Flask-Potion',
    version='0.16.0',
    packages=find_packages(exclude=['*tests*']),
    url='http://potion.readthedocs.org/en/latest/',
    license='MIT',
    author='Lars Schöning',
    author_email='lars@lyschoening.de',
    description='Powerful REST API framework for Flask and SQLAlchemy',
    long_description=codecs.open('README.rst', encoding='utf-8').read(),
    test_suite='nose.collector',
    tests_require=tests_require,
    install_requires=[
        'Flask>=0.10',
        'jsonschema>=2.4.0',
        'aniso8601>=0.84',
        'blinker>=1.3',
        'six>=1.8.0',
        'rfc3987',
        'strict-rfc3339'
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    zip_safe=False,
    extras_require={
        'docs': ['sphinx', 'Flask-Principal', 'Flask-SQLAlchemy', 'peewee'],
        'principal': [
            'Flask-Principal',
        ],
        'sqlalchemy': [
            'Flask-SQLAlchemy>=2.0'
        ],
        'peewee': [
            'peewee==2.*'
        ],
        'mongoengine': [
            'Flask-MongoEngine>=0.7.0'
        ],
        'tests': tests_require,
    }
)
