# coding: utf8
"""
    weasysuite.auto
    ---------------

    A script setting results of tests with ignored flags and references.

    :copyright: Copyright 2011-2012 Simon Sapin, 2013 Kozea
    :license: BSD, see LICENSE for details.

"""

from __future__ import division, unicode_literals, print_function

import sys
import os.path
import logging
import traceback
import pystacia
from datetime import datetime

from weasyprint import HTML, CSS

from web import (
    read_testinfo, save_test, prepare_test_data, FOLDER, EXTENSION,
    OUTPUT_FOLDER, BASE_PATH, BASE_URL, REFERENCES)


PAGE_SIZE_STYLESHEET = CSS(string='''
    @page { margin: 0; size: 640px }
''')

IGNORED_FLAGS = {'animation', 'scroll', 'interact', 'dom'}


def make_test_suite():
    rendered = {}  # Memoize

    def render(name):
        raw = rendered.get(name)
        if raw is None:
            # name is sometimes "support/something.htm"
            basename = os.path.basename(name)
            png_filename = os.path.join(OUTPUT_FOLDER, basename + '.png')
            HTML(BASE_URL + name).write_png(
                png_filename, stylesheets=[PAGE_SIZE_STYLESHEET])
            raw = pystacia.read(png_filename).get_raw('RGBA')['raw']
            rendered[name] = raw
        return raw

    flags_by_id = {
        '.'.join(test['test_id'], EXTENSION[:3]): test['flags']
        for test in read_testinfo(BASE_PATH)}

    for test, equal_references in REFERENCES.items():
        for equal, references in equal_references.items():
            # Use default parameter values to bind to the current values,
            # not to the variables as a closure would do.
            def test_function(equal=equal, test=test, references=references):
                test_render = render(test)
                references_render = map(render, references)
                return all((test_render != ref_render) ^ equal
                           for ref_render in references_render)
            if not set(flags_by_id[test]).intersection(IGNORED_FLAGS):
                yield test, test_function


if __name__ == '__main__':
    logger = logging.getLogger('weasyprint')
    del logger.handlers[:]
    logger.addHandler(logging.NullHandler())

    # Tests with reference(s)
    reference_tests = list(make_test_suite())
    passed = 0
    failed = 0
    errors = 0
    try:
        for i, (name, test) in enumerate(reference_tests, 1):
            line = {
                'test_id': name, 'result': None, 'comment': '',
                'date': datetime(*datetime.utcnow().timetuple()[:6])}
            print('Test %i of %i: %s ' % (
                i, len(reference_tests), name), end='')
            sys.stdout.flush()
            try:
                test_passed = test()
            except Exception:
                print('ERROR:')
                traceback.print_exc()
                errors += 1
                line['result'] = 'fail'
                line['comment'] = 'Crash'
            else:
                if test_passed:
                    print('PASS')
                    passed += 1
                    line['result'] = 'pass'
                else:
                    print('FAIL')
                    failed += 1
                    line['result'] = 'fail'
            save_test('css2.1', line)
    except KeyboardInterrupt:
        pass
    print('')
    print('Passed: %i, failed: %i, errors: %i' % (passed, failed, errors))

    # Tests with ignored flags
    suites, tests_by_link = prepare_test_data(FOLDER)
    ignored_tests = [test for test in suites['css2.1']['tests']]
    for name in ignored_tests:
        test = suites['css2.1']['tests'][name]
        if set(test['flags']).intersection(IGNORED_FLAGS):
            line = {
                'test_id': name, 'result': 'na', 'comment': '',
                'date': datetime(*datetime.utcnow().timetuple()[:6])}
            save_test('css2.1', line)
