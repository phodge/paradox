from setuptools import setup


def _read_pyproject():
    from os.path import dirname, join

    import pytoml

    try:
        with open(join(dirname(__file__), 'pyproject.toml')) as f:
            pyproject = pytoml.load(f)
    except FileNotFoundError:
        # it looks like setuptools renames the file while it's working ... what a dirty hack job
        with open(join(dirname(__file__), 'pyproject.tmp')) as f:
            pyproject = pytoml.load(f)

    try:
        return pyproject['tool']['poetry']
    except KeyError:
        raise Exception("pyproject.toml is missing [tool.poetry] section")


def _get_packages_recursive(poetry):
    from glob import glob
    from os.path import dirname

    for entry in poetry['packages']:
        subdir = entry['include']
        yield subdir

        # look for subdirectories
        for initpy in glob(subdir + '/**/__init__.py'):
            yield dirname(initpy)


poetry = _read_pyproject()

setup(
    name=poetry['name'],
    version=poetry['version'],
    description=poetry['description'],
    packages=list(_get_packages_recursive(poetry)),
    package_data=['py.typed'],
    include_package_data=True,
    # TODO: how about dependencies?
    install_requires=[
        packagename
        for packagename in poetry['dependencies']
        if packagename != 'python'
    ],
)
