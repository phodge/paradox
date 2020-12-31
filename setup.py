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


poetry = _read_pyproject()

setup(
    name=poetry['name'],
    version=poetry['version'],
    description=poetry['description'],
    packages=[
        entry['include']
        for entry in poetry['packages']
    ],
    # TODO: how about dependencies?
    install_requires=[
        packagename
        for packagename in poetry['dependencies']
        if packagename != 'python'
    ],
)
