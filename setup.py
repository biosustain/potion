# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from setuptools import setup

setup(
    name='potion',
    version='0.0.0',
    packages=['flask_potion'],
    url='',
    license='MIT',
    author='Lars Schöning',
    author_email='lays@biosustain.dtu.dk',
    description='',
    install_requires=[
        'Flask>=0.10',
        'Flask-SQLAlchemy>=1.0',
        'jsonschema>=2.3.0',
        'iso8601>=0.1.8',
        'blinker>=1.3',
        'six>=1.3.0'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    zip_safe=False,
    extras_require={
        'docs': ['sphinx', 'Flask-Principal'],
        'principal': [
            'Flask-Principal',
        ]
    }
)
