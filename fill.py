#!/usr/bin/env python
"""
weasysuite.fill
---------------

A script filling the results of tests by comparing output PNG files from
different versions.

:copyright: Copyright 2011-2012 Simon Sapin, 2013-2015 Kozea
:license: BSD, see LICENSE for details.

"""

import os
from datetime import datetime

from web import prepare_test_data, save_test, FOLDER, OUTPUT_FOLDER, VERSION

versions = sorted(os.listdir(os.path.join(FOLDER, 'results')))
OLD_VERSION = versions[versions.index(VERSION) - 1]

suites, _ = prepare_test_data(FOLDER, version=VERSION)
old_suites, _ = prepare_test_data(FOLDER, version=OLD_VERSION)

suite_source = os.path.join(suites['css2.1']['path'], 'html4')

print('Filling %s from %s' % (VERSION, OLD_VERSION))
for i, (name, test) in enumerate(old_suites['css2.1']['tests'].items()):
    print(str(i + 1) + ' Comparing ' + name)
    image_filename = os.path.join(OUTPUT_FOLDER, name + '.png')
    old_image_filename = image_filename.replace(
        '/%s/' % VERSION, '/%s/' % OLD_VERSION)
    if test['result'] == 'na' or (
            os.path.exists(old_image_filename) and
            os.path.exists(image_filename) and
            open(image_filename, 'rb').read() ==
            open(old_image_filename, 'rb').read()):
        test['date'] = datetime(*datetime.utcnow().timetuple()[:6])
        save_test('css2.1', test)
