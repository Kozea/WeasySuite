#!/usr/bin/env python
"""
weasysuite.web
--------------

A simple web application to run, inspect and save the results of
the W3C CSS Test Suites.

See http://test.csswg.org/suites/
    http://www.w3.org/Style/CSS/Test/
    http://test.csswg.org/

:copyright: Copyright 2011-2012 Simon Sapin, 2013-2015 Kozea
:license: BSD, see LICENSE for details.

"""

import os
import sys
import fileinput
import io
import json
import optparse
from base64 import b64encode
from datetime import datetime
from urllib.request import urlopen
from zipfile import ZipFile

import lxml.html
from weasyprint import HTML, CSS, VERSION
from flask import (
    Flask, render_template, abort, send_from_directory, safe_join,
    redirect, request, url_for)


parser = optparse.OptionParser(version=VERSION)
parser.add_option('-V', '--weasyprint-version', default=VERSION)
options = parser.parse_args()[0]
if options.weasyprint_version:
    VERSION = options.weasyprint_version

STYLESHEET = CSS(string='''
    @page { margin: 0; size: 680px }
    body { margin: 20px }
    :root { image-rendering: optimizespeed }''')
FOLDER = os.path.dirname(__file__)
OUTPUT_FOLDER = os.path.join(FOLDER, 'results', VERSION, 'png')
BASE_PATH = os.path.join(FOLDER, 'suites')


SUITES = {}
REFERENCES = {}

try:
    ALL_SUITES = json.load(open(os.path.join(BASE_PATH, 'suites.json')))
except:
    ALL_SUITES = {}


def add_suite(suite):
    if suite in SUITES:
        del SUITES[suite]
    suite_path = os.path.join(BASE_PATH, suite)
    if not os.path.isdir(suite_path):
        return
    date, = os.listdir(suite_path)
    formats = set(os.listdir(os.path.join(BASE_PATH, suite, date)))
    format = [format for format in formats if format.startswith('html')].pop()
    name = suite
    if ALL_SUITES.get(suite):
        name = ALL_SUITES[suite].get('name', suite)
    SUITES[suite] = {'date': date, 'format': format, 'name': name}
    filename = os.path.join(
        BASE_PATH, suite, date, SUITES[suite]['format'], 'reftest.list')
    with open(filename) as fd:
        for line in fd.readlines():
            # Remove comments
            line = line.split('#', 1)[0]
            if not line.strip():
                # Comment-only line
                return
            parts = line.split()
            if parts[0] in ('==', '!='):
                comparaison_index = 0
                test_index = 1
            elif parts[1] in ('==', '!='):
                comparaison_index = 1
                test_index = 0
            else:
                raise ValueError(line)
            comparaison = parts[comparaison_index]
            equal = comparaison == '=='
            test = parts[test_index].split('.')[0]
            references = [part.split('.')[0] for part in parts[2:]]
            assert references, 'No reference'
            if test not in REFERENCES:
                REFERENCES[test] = {}
            REFERENCES[test][equal] = references


def read_testinfo(suite_directory):
    with open(os.path.join(suite_directory, 'testinfo.data')) as fd:
        lines = iter(fd)
        next(lines)  # skip labels
        for line in lines:
            test_id, references, title, flags, links, _, _, assertion = (
                line.strip(' \n').split('\t'))
            yield dict(
                test_id=test_id.lower(), assertion=assertion, title=title,
                flags=flags.split(',') if flags else None,
                links=links.split(',') if links else None,
                references=REFERENCES.get(test_id, {}))


def read_chapter(filename, tests_by_link):
    index_filename = os.path.join(
        os.path.dirname(os.path.dirname(filename)), 'index.html')
    if not os.path.isfile(index_filename):
        index_filename = index_filename[:-1]
    url_prefix = lxml.html.parse(index_filename).xpath(
        '//a[starts-with(@href, "http://www.w3.org/TR/")]')[0].get('href')
    for link in lxml.html.parse(filename).xpath(
            '//th/a[starts-with(@href, "%s")]' % url_prefix):
        url = link.get('href')[len(url_prefix):]
        if url in tests_by_link:
            yield (
                link.text_content().strip(), link.get('href'),
                tests_by_link[url])


def read_toc(suite_directory, tests_by_link):
    suite = os.path.basename(os.path.dirname(suite_directory))
    suite_directory = os.path.join(suite_directory, SUITES[suite]['format'])
    filename = os.path.join(suite_directory, 'toc.html')
    if not os.path.isfile(filename):
        filename = filename[:-1]
    for link in lxml.html.parse(filename).xpath('//table//a[@href]'):
        filename = os.path.join(suite_directory, link.get('href'))
        sections = list(read_chapter(filename, tests_by_link))
        if sections:
            num = sum(len(tests) for _, _, tests in sections)
            yield (link.text_content().strip(), sections, num)


def prepare_test_data(suite_directory, version=VERSION):
    suites = {}
    suites_directory = os.path.abspath(os.path.join(suite_directory, 'suites'))
    for suite in os.listdir(suites_directory):
        suite_path = os.path.join(suites_directory, suite)
        if not os.path.isdir(suite_path):
            continue
        tests_by_link = {}
        date, = os.listdir(suite_path)
        path = os.path.join(suites_directory, suite, date)
        tests = {}
        for test in read_testinfo(path):
            for link in test['links']:
                link = link.split('/')[-1]
                tests[test['test_id']] = test
                tests_by_link.setdefault(link, []).append(test)
        chapters = list(read_toc(path, tests_by_link))
        suites[suite] = {'path': path, 'tests': tests, 'chapters': chapters}

        filename = os.path.join(FOLDER, 'results', version, suite)
        if os.path.isfile(filename):
            results = iter(open(filename).readlines())
        else:
            results = []

        for result_line in results:
            result_line = result_line[:-1]
            if result_line.startswith(SUITES[suite]['format']):
                name, result, comment = result_line.split('\t', 2)
                if '\t' in comment:
                    comment, date = comment.split('\t')
                    date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                else:
                    date = None
                format, test_id = name.split('/')
                if format == SUITES[suite]['format']:
                    test_id_parts = test_id.split('.')
                    for i in range(len(test_id_parts)):
                        test_id = '.'.join(test_id_parts[:-i])
                        if test_id in tests:
                            break
                    tests[test_id]['result'] = result
                    tests[test_id]['comment'] = comment
                    tests[test_id]['date'] = date

        for test in tests:
            if 'result' not in tests[test]:
                tests[test]['result'] = 'unavailable'
                tests[test]['comment'] = None
                tests[test]['date'] = None

    return suites


def save_test(suite, test):
    format = SUITES[suite]['format']
    filename = os.path.join(FOLDER, 'results', VERSION, suite)
    for line in fileinput.input(filename, inplace=1):
        if line.startswith('/'.join((format, test['test_id'] + '.'))):
            line = '\t'.join((
                line.split('\t')[0], test['result'] or '?',
                test['comment'] or '', str(test['date']))) + '\n'
        sys.stdout.write(line)


app = Flask(__name__)


@app.route('/', methods=('GET', 'POST'))
def toc():
    if request.method == 'POST':
        data = urlopen('http://test.csswg.org/suites/')
        suites = [
            link.get('href')[:-5] for link in
            lxml.html.parse(data).xpath('//a')
            if link.get('href').endswith('_dev/')]
        for suite in suites:
            if suite not in ALL_SUITES:
                ALL_SUITES[suite] = None
        with open(os.path.join(BASE_PATH, 'suites.json'), 'w') as fd:
            json.dump(ALL_SUITES, fd)
    missing_suites = [suite for suite in ALL_SUITES if suite not in SUITES]
    return render_template(
        'toc.html.jinja2', suites=SUITES, missing_suites=missing_suites)


@app.route('/suite-<suite>/')
def suite(suite):
    suite_name = SUITES[suite]['name']
    return render_template(
        'suite.html.jinja2', suite=suite, suite_name=suite_name,
        tests=suites[suite]['tests'].values(),
        chapters=suites[suite]['chapters'],
        total=len(suites[suite]['tests']))


@app.route('/download-suite-<suite>/')
def download_suite(suite):
    data = urlopen('http://test.csswg.org/suites/%s_dev/' % suite)
    versions = [
        link.get('href')[:-1] for link in lxml.html.parse(data).xpath('//a')
        if link.get('href').endswith('/')]
    if 'latest' in versions:
        version = 'latest'
    else:
        assert 'nightly-unstable' in versions
        version = 'nightly-unstable'
    zip_data = urlopen(
        'http://test.csswg.org/suites/%s_dev/%s.zip' % (suite, version))
    zip_file = ZipFile(io.BytesIO(zip_data.read()))
    os.mkdir(os.path.join(BASE_PATH, suite))
    zip_file.extractall(os.path.join(BASE_PATH, suite))
    folder, = os.listdir(os.path.join(BASE_PATH, suite))
    index_file, = [
        filename for filename in
        os.listdir(os.path.join(BASE_PATH, suite, folder))
        if filename.startswith('index.htm')]
    name, = [
        title.text for title in
        lxml.html.parse(os.path.join(BASE_PATH, suite, folder, index_file))
        .xpath('//title')]
    if name.endswith(' Test Suite'):
        name = name[:-11]
    if name.endswith(' Conformance'):
        name = name[:-12]
    add_suite(suite)
    prepare_test_data(FOLDER)
    ALL_SUITES[suite] = {'name': name}
    with open(os.path.join(BASE_PATH, 'suites.json'), 'w') as fd:
        json.dump(ALL_SUITES, fd)
    return redirect(url_for('suite', suite=suite))


@app.route('/suite-<suite>/results/')
def suite_results(suite):
    suite_name = SUITES[suite]['name']
    all_suites = {}
    for version in os.listdir(os.path.join(FOLDER, 'results')):
        all_suites[version] = prepare_test_data(FOLDER, version=version)
    chapters = all_suites[VERSION][suite]['chapters']
    results = {}
    number = 0
    for version in all_suites:
        results[version] = {'pass': 0, 'fail': 0, 'count': 0}
    for (name, sections, test_number) in chapters:
        for name, link, tests in sections:
            for test in tests:
                number += 1
                for version in all_suites:
                    version_test = (
                        all_suites[version][suite]['tests'][test['test_id']])
                    if version_test['result'] != '?':
                        results[version]['count'] += 1
                    if version_test['result'] in results[version]:
                        results[version][version_test['result']] += 1

    return render_template(
        'suite_results.html.jinja2', all_suites=all_suites, suite=suite,
        suite_name=suite_name, chapters=chapters, number=number,
        results=results)


@app.route('/suite-<suite>/chapter<int:chapter_num>/section<int:section_num>/')
def section(suite, chapter_num, section_num):
    suite_name = SUITES[suite]['name']
    try:
        chapter, sections, _ = suites[suite]['chapters'][chapter_num - 1]
        title, url, tests = sections[section_num - 1]
    except IndexError:
        abort(404)
    return render_template('section.html.jinja2', **locals())


@app.route('/test/suite-<suite>/<test_id>/')
@app.route('/suite-<suite>/chapter<int:chapter_num>/'
           'section<int:section_num>/test<int:test_index>/',
           methods=('GET', 'POST'))
def run_test(suite, chapter_num=None, section_num=None, test_index=None,
             test_id=None):
    suite_name = SUITES[suite]['name']
    if test_id is None:
        try:
            chapter, sections, _ = suites[suite]['chapters'][chapter_num - 1]
            section, url, tests = sections[section_num - 1]
            if len(tests) == test_index - 1:
                return redirect(url_for(
                    'section', suite=suite, chapter_num=chapter_num,
                    section_num=section_num))
            test = tests[test_index - 1]
            test_id = test['test_id']
            previous_index = test_index - 1
            next_index = test_index + 1 if test_index < len(tests) else None
        except IndexError:
            abort(404)
    else:
        test = dict(test_id=test_id)

    if request.method == 'POST':
        test['date'] = datetime(*datetime.utcnow().timetuple()[:6])
        if request.form.get('next-result'):
            test['result'] = request.form['next-result']
            save_test(suite, test)
            return redirect(url_for(
                'run_test', suite=suite, chapter_num=chapter_num,
                section_num=section_num, test_index=test_index + 1))
        else:
            test['result'] = request.form['result']
            test['comment'] = request.form['comment'].strip()
            save_test(suite, test)
            return redirect(request.path)

    from pygments import highlight
    from pygments.lexers import HtmlLexer
    from pygments.formatters import HtmlFormatter

    folder = safe_join(suites[suite]['path'], SUITES[suite]['format'])
    filenames = [
        filename for filename in os.listdir(folder)
        if filename.lower().startswith(test_id + '.')]
    if filenames:
        filename = safe_join(folder, filenames[0])
        with open(filename, 'rb') as fd:
            try:
                source = fd.read().decode('utf8')
            except UnicodeDecodeError:
                source = 'Non UTF-8 content'

        formatter = HtmlFormatter(linenos='inline')
        source = highlight(source, HtmlLexer(), formatter)
        css = formatter.get_style_defs('.highlight')
    stylesheet = request.args.get('stylesheet')
    media_type = request.args.get('media_type')
    return render_template('run_test.html.jinja2', **locals())


@app.route('/render/suite-<suite>/<path:test_id>')
@app.route('/render/suite-<suite>/<path:test_id>/media-<media_type>')
@app.route('/render/suite-<suite>/<path:test_id>/style-<stylesheet>')
def render(suite, test_id, media_type='print', stylesheet=None):
    folder = safe_join(suites[suite]['path'], SUITES[suite]['format'])
    stylesheets = [STYLESHEET]
    if stylesheet:
        stylesheets.append(os.path.join(folder, 'support', stylesheet))
    if '/' in test_id:
        folder = os.path.join(folder, os.path.dirname(test_id))
        test_id = os.path.basename(test_id)
    filename, = [
        filename for filename in os.listdir(folder)
        if filename.lower().startswith(test_id + '.')]
    filename = safe_join(folder, filename)
    document = (
        HTML(filename, encoding='utf8', media_type=media_type)
        .render(stylesheets=stylesheets, enable_hinting=True))
    pages = [
        'data:image/png;base64,' +
        b64encode(document.copy([page]).write_png()[0]).decode()
        for page in document.pages]
    return render_template('render.html.jinja2', **locals())


@app.route('/test-data/suite-<suite>/<path:filename>')
def test_data(suite, filename):
    return send_from_directory(
        safe_join(suites[suite]['path'], SUITES[suite]['format']), filename)


if __name__ == '__main__':
    print('Tested version is %s' % VERSION)
    for suite in os.listdir(BASE_PATH):
        add_suite(suite)
    suites = prepare_test_data(FOLDER)
    app.run(debug=True)
