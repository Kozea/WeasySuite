#!/usr/bin/env python
"""
weasysuite.generate
-------------------

A script generating PNG images for all tests.

:copyright: Copyright 2011-2012 Simon Sapin, 2013-2016 Kozea
:license: BSD, see LICENSE for details.

"""

import logging
import os
import re
import sys
import time
import shutil
import traceback

from weasyprint import HTML

from web import (
    add_suite, BASE_PATH, SUITES, STYLESHEET, OUTPUT_FOLDER, VERSION)


logging.getLogger('weasyprint').setLevel(100)

print('Testing version %s' % VERSION)

if os.path.exists(OUTPUT_FOLDER):
    print('\nI\'M GOING TO REMOVE OLD TEST RESULTS IN 10 SECONDS!\n')
    for i in range(10):
        print(10 - i, end=' ')
        sys.stdout.flush()
        time.sleep(1)
    shutil.rmtree(OUTPUT_FOLDER)

os.makedirs(OUTPUT_FOLDER)

for suite in os.listdir(BASE_PATH):
    add_suite(suite)

CRASHES = []

for suite_name, suite in SUITES.items():
    print('\n\n\n## {} ##\n'.format(suite['name']))
    for chapter_name, sections, test_number in suite['chapters']:
        print('\n# {} #'.format(re.sub('[\n ]+', ' ', chapter_name)))
        for section_name, link, tests in sections:
            print(section_name, end=' ')
            for test in tests:
                test_id = test['test_id']
                image_filename = os.path.join(
                    OUTPUT_FOLDER, '{}.png'.format(test_id))
                filenames = [
                    filename for filename in os.listdir(suite['path'])
                    if os.path.splitext(filename.lower())[0] == test_id]
                if filenames:
                    filename = os.path.join(suite['path'], filenames[0])
                    try:
                        document = HTML(filename, encoding='utf8').write_png(
                            image_filename, stylesheets=[STYLESHEET],
                            presentational_hints=True)
                    except KeyboardInterrupt as error:
                        raise error
                    except:
                        print('C', end='')
                        crash_filename = '{}.txt'.format(image_filename)
                        CRASHES.append('%s - %s - %s - %s' % (
                            suite_name, chapter_name, section_name, test_id))
                        with open(crash_filename, 'w') as fd:
                            fd.write(traceback.format_exc())
                    else:
                        print('.', end='')
                    sys.stdout.flush()
            print()

if CRASHES:
    print('\n\n\nCrashes:')
    for crash in CRASHES:
        print(crash)
