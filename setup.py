from typing import Any, Dict

from setuptools import setup


def _read_pyproject() -> Dict[str, Any]:
    from os.path import dirname, join

    import pytoml

    with open(join(dirname(__file__), 'pyproject.toml')) as f:
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
