from setuptools import find_packages, setup

tests_requirements = [
    'pytest',
    'pytest-cov',
    'pytest-flake8',
    'pytest-isort',
]

setup(
    name="WeasySuite",
    version="0.1.dev0",
    description="Test WeasyPrint with the W3C test suites.",
    url="http://test.weasyprint.org",
    author="Kozea",
    packages=find_packages(),
    include_package_data=True,
    scripts=['web.py', 'fill.py', 'generate.py'],
    install_requires=[
        'flask',
        'lxml',
        'pygments',
        'weasyprint',
    ],
    tests_require=tests_requirements,
    extras_require={'test': tests_requirements}
)
