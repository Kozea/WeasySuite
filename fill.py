#!/usr/bin/env python
"""
weasysuite.fill
---------------

A script filling the results of tests by comparing output PNG files from
different versions.

:copyright: Copyright 2011-2012 Simon Sapin, 2013-2016 Kozea
:license: BSD, see LICENSE for details.

"""

import os
import sys
import time
from datetime import datetime

from web import (
    BASE_PATH, FOLDER, OUTPUT_FOLDER, SUITES, VERSION, add_suite, options,
    save_test)


versions = sorted(os.listdir(os.path.join(FOLDER, 'results')))
OLD_VERSION = versions[versions.index(VERSION) - 1]

print('Testing version {} from {}'.format(VERSION, OLD_VERSION))

print('\nI\'M GOING TO OVERWRITE TEST RESULTS IN 10 SECONDS!\n')
for i in range(10):
    print(10 - i, end=' ')
    sys.stdout.flush()
    time.sleep(1)

for suite in options.suites or os.listdir(BASE_PATH):
    add_suite(suite)

for suite_name, suite in SUITES.items():
    print('\n\n\n## {} ##\n'.format(suite['name']))
    for name, test in suite['results'][OLD_VERSION].items():
        image_filename = os.path.join(OUTPUT_FOLDER, name + '.png')
        old_image_filename = image_filename.replace(
            '/%s/' % VERSION, '/%s/' % OLD_VERSION)
        flags = test['flags'] or []
        if test['result'] == 'na' or (
                os.path.exists(old_image_filename) and
                os.path.exists(image_filename) and
                open(image_filename, 'rb').read() ==
                open(old_image_filename, 'rb').read() and
                test['result'] != '?'):
            test['date'] = datetime(*datetime.utcnow().timetuple()[:6])
            save_test(suite_name, test)
            print('.', end='')
        elif 'dom' in flags or 'script' in flags or 'interact' in flags:
            test['date'] = datetime(*datetime.utcnow().timetuple()[:6])
            test['result'] = 'na'
            save_test(suite_name, test)
            print('n', end='')
        else:
            print('!', end='')
        sys.stdout.flush()
