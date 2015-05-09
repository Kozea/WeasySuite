#!/usr/bin/env python
"""
weasysuite.generate
-------------------

A script generating PNG images for all tests.

:copyright: Copyright 2011-2012 Simon Sapin, 2013 Kozea
:license: BSD, see LICENSE for details.

"""

import os
import traceback

from weasyprint import HTML

from web import prepare_test_data, FOLDER, OUTPUT_FOLDER, STYLESHEET


suites, tests_by_link = prepare_test_data(FOLDER)

# TODO: make this work with other suites
suite_source = os.path.join(suites['css21']['path'], 'html4')

for i, (name, test) in enumerate(suites['css21']['tests'].items()):
    print(str(i + 1) + ' Tesing ' + name)
    image_filename = os.path.join(OUTPUT_FOLDER, name + '.png')
    if os.path.exists(image_filename):
        print('Skipping ' + name)
        continue
    try:
        filename, = [
            filename for filename
            in os.listdir(suite_source) if filename.startswith(name + '.')]
        HTML(os.path.join(suite_source, filename), encoding='utf8').write_png(
            image_filename, stylesheets=[STYLESHEET])
    except:
        print('Crash')
        with open(os.path.join(OUTPUT_FOLDER, name + '.txt'), 'w') as fd:
            fd.write(traceback.format_exc())
