# coding: utf8
"""
    weasysuite.web
    --------------

    A simple web application to run, inspect and save the results of
    the W3C CSS Test Suites.

    See http://test.csswg.org/suites/
        http://www.w3.org/Style/CSS/Test/
        http://test.csswg.org/

    :copyright: Copyright 2011-2012 Simon Sapin, 2013 Guillaume Ayoub
    :license: BSD, see LICENSE for details.

"""

from __future__ import division, unicode_literals

import os
import sys
import fileinput
from datetime import datetime

import lxml.html
from flask import (
    Flask, render_template, abort, send_from_directory, safe_join,
    redirect, request, url_for)

from weasyprint import HTML, CSS, VERSION

STYLESHEET = CSS(string='''
    @page { margin: 20px; size: 680px }
    body { margin: 0 }
''')
FOLDER = os.path.dirname(__file__)
OUTPUT_FOLDER = os.path.join(FOLDER, 'results', VERSION, 'css2.1-png')
# Changing these values isn't enough to test another format, but it's better
# than nothing
FORMAT = 'html4'
EXTENSION = 'html'
# TODO: make this work with different suites
BASE_PATH = os.path.join(FOLDER, 'suites', 'css2.1', '20110323')
BASE_URL = 'file://' + os.path.join(BASE_PATH, FORMAT, '')


REFERENCES = {}
with open(os.path.join(BASE_PATH, FORMAT, 'reftest.list')) as fd:
    for line in fd.readlines():
        line = line.decode('ascii')
        # Remove comments
        line = line.split('#', 1)[0]
        if not line.strip():
            # Comment-only line
            continue
        parts = line.split()
        comparaison = parts[0]
        if comparaison == '==':
            equal = True
        elif comparaison == '!=':
            equal = False
        else:
            raise ValueError(line)
        test = parts[1].split('.')[0]
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
            test_id, references, title, flags, links, _, _, assertion = \
                line.strip(' \n').split('\t')
            yield dict(
                test_id=test_id, assertion=assertion, title=title,
                flags=(flags or '').split(','),
                links=(links or '').split(','),
                references=REFERENCES.get(test_id, {}))


def read_chapter(filename, tests_by_link):
    # TODO: fix this CSS21-only line
    url_prefix = 'http://www.w3.org/TR/CSS21/'
    for link in lxml.html.parse(filename).xpath(
            '//th/a[starts-with(@href, "%s")]' % url_prefix):
        url = link.get('href')[len(url_prefix):]
        if url in tests_by_link:
            yield (
                link.text_content().strip(), link.get('href'),
                tests_by_link[url])


def read_toc(suite_directory, tests_by_link):
    suite_directory = os.path.join(suite_directory, FORMAT)
    filename = os.path.join(suite_directory, '.'.join(('toc', EXTENSION)))
    for link in lxml.html.parse(filename).xpath('//table//a[@href]'):
        filename = os.path.join(suite_directory, link.get('href'))
        sections = list(read_chapter(filename, tests_by_link))
        if sections:
            num = sum(len(tests) for _, _, tests in sections)
            yield (link.text_content().strip(), sections, num)


def prepare_test_data(suite_directory, version=VERSION):
    suites = {}
    tests_by_link = {}
    suites_directory = os.path.join(suite_directory, 'suites')
    for suite in os.listdir(suites_directory):
        date, = os.listdir(os.path.join(suites_directory, suite))
        path = os.path.join(suites_directory, suite, date)
        tests = {}
        for test in read_testinfo(path):
            for link in test['links']:
                tests[test['test_id']] = test
                tests_by_link.setdefault(link, []).append(test)
        chapters = list(read_toc(path, tests_by_link))
        suites[suite] = {'path': path, 'tests': tests, 'chapters': chapters}

        results = iter(open(
            os.path.join(FOLDER, 'results', version, suite)).readlines())

        for result_line in results:
            result_line = result_line[:-1]
            if result_line.startswith(FORMAT):
                name, result, comment = result_line.split('\t', 2)
                if '\t' in comment:
                    comment, date = comment.split('\t')
                    date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                else:
                    date = None
                format, test_id = name.split('/')
                if format == FORMAT:
                    test_id = test_id.split('.')[0]
                    tests[test_id]['result'] = result
                    tests[test_id]['comment'] = comment
                    tests[test_id]['date'] = date

        for test in tests:
            if 'result' not in tests[test]:
                tests[test]['result'] = 'not available'
                tests[test]['comment'] = None
                tests[test]['date'] = None

    return suites, tests_by_link


def save_test(suite, test):
    filename = os.path.join(FOLDER, 'results', VERSION, suite)
    for line in fileinput.input(filename, inplace=1):
        if line.startswith('/'.join((FORMAT, test['test_id'] + '.'))):
            line = '\t'.join((
                line.split('\t')[0], test['result'] or '?',
                test['comment'] or '', str(test['date']))) + '\n'
        sys.stdout.write(line)


def run(suite_directory):
    suites, tests_by_link = prepare_test_data(suite_directory)

    app = Flask(__name__)
    app.jinja_env.globals['len'] = len

    @app.route('/')
    def toc():
        return render_template('.'.join(('toc', EXTENSION)), suites=suites)

    @app.route('/suite-<suite>/')
    def suite(suite):
        return render_template(
            'suite.html', suite=suite, tests=suites[suite]['tests'].values(),
            chapters=enumerate(suites[suite]['chapters'], 1),
            total=len(suites[suite]['tests']))

    @app.route('/suite-<suite>/results/')
    def suite_results(suite):
        all_suites = {}
        for version in os.listdir(os.path.join(FOLDER, 'results')):
            all_suites[version], _ = prepare_test_data(
                suite_directory, version=version)
        chapters = all_suites[VERSION][suite]['chapters']
        results = {}
        number = 0
        for version in all_suites:
            results[version] = {'pass': 0, 'count': 0}
        for (name, sections, test_number) in chapters:
            for name, link, tests in sections:
                for test in tests:
                    number += 1
                    for version in all_suites:
                        version_test = (all_suites[version][suite]
                                        ['tests'][test['test_id']])
                        if version_test['result'] != '?':
                            results[version]['count'] += 1
                        if version_test['result'] == 'pass':
                            results[version]['pass'] += 1

        print(results)
        return render_template(
            'suite_results.html', all_suites=all_suites, suite=suite,
            chapters=chapters, number=number, results=results)

    @app.route('/suite-<suite>/chapter<int:chapter_num>/')
    def chapter(suite, chapter_num):
        try:
            title, sections, _ = suites[suite]['chapters'][chapter_num - 1]
        except IndexError:
            abort(404)
        return render_template(
            'chapter.html', suite=suite, chapter_num=chapter_num,
            chapter=title, sections=enumerate(sections, 1))

    @app.route('/suite-<suite>/chapter<int:chapter_num>/'
               'section<int:section_num>/')
    def section(suite, chapter_num, section_num):
        try:
            chapter, sections, _ = suites[suite]['chapters'][chapter_num - 1]
            title, url, tests = sections[section_num - 1]
        except IndexError:
            abort(404)
        return render_template('section.html', **locals())

    @app.route('/test/suite-<suite>/<test_id>/')
    @app.route('/suite-<suite>/chapter<int:chapter_num>/'
               'section<int:section_num>/test<int:test_index>/',
               methods=('GET', 'POST'))
    def run_test(suite, chapter_num=None, section_num=None,
                 test_index=None, test_id=None):
        if test_id is None:
            try:
                chapter, sections, _ = \
                    suites[suite]['chapters'][chapter_num - 1]
                title, url, tests = sections[section_num - 1]
                test = tests[test_index - 1]
                test_id = test['test_id']
                previous_index = test_index - 1
                next_index = \
                    test_index + 1 if test_index < len(tests) else None
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

        folder = safe_join(suites[suite]['path'], FORMAT)
        filenames = [
            filename for filename
            in os.listdir(folder) if filename.startswith(test_id + '.')]
        if filenames:
            filename = safe_join(folder, filenames[0])
            with open(filename, 'rb') as fd:
                try:
                    source = fd.read().decode('utf8')
                except UnicodeDecodeError:
                    source = "Non UTF-8 content"

            formatter = HtmlFormatter(linenos='inline')
            source = highlight(source, HtmlLexer(), formatter)
            css = formatter.get_style_defs('.highlight')
        stylesheet = request.args.get('stylesheet')
        media_type = request.args.get('media_type')
        return render_template('run_test.html', **locals())

    @app.route('/render/suite-<suite>/<path:test_id>')
    @app.route('/render/suite-<suite>/<path:test_id>/media-<media_type>')
    @app.route('/render/suite-<suite>/<path:test_id>/style-<stylesheet>')
    def render(suite, test_id, media_type='print', stylesheet=None):
        folder = safe_join(suites[suite]['path'], FORMAT)
        stylesheets = [STYLESHEET]
        if stylesheet:
            stylesheets.append(os.path.join(folder, 'support', stylesheet))
        filename, = [
            filename for filename
            in os.listdir(folder) if filename.startswith(test_id + '.')]
        filename = safe_join(folder, filename)
        document = (
            HTML(filename, encoding='utf8', media_type=media_type)
            .render(stylesheets=stylesheets, enable_hinting=True))
        pages = [
            'data:image/png;base64,' + document.copy([page])
            .write_png()[0].encode('base64').replace('\n', '')
            for page in document.pages]
        return render_template('render.html', **locals())

    @app.route('/test-data/suite-<suite>/<path:filename>')
    def test_data(suite, filename):
        return send_from_directory(
            safe_join(suites[suite]['path'], FORMAT), filename)

    app.run(debug=True)


if __name__ == '__main__':
    print('Tested version is %s' % VERSION)
    run(FOLDER)
