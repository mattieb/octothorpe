#!/usr/bin/env python

from distutils.core import setup


setup(
    name='octothorpe',
    version='0.1',
    description='Asterisk Manager Interface library for the Twisted engine',
    author='Matt Behrens',
    author_email='matt@zigg.com',
    url='http://www.zigg.com/code/octothorpe/',
    packages=['octothorpe'],
    requires=['Twisted'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Framework :: Twisted',
        'License :: OSI Approved :: MIT License',
        'Topic :: Communications :: Telephony',
    ],
)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
