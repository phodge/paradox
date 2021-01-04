from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_all_modules_can_be_imported() -> None:
    from importlib import import_module

    modulenames = []

    for path in ROOT.glob('paradox/**/*.py'):

        # replace '/' with '.' to form a module path
        modulename = str(path.relative_to(ROOT)).replace('/', '.')

        # strip .py from the end
        assert modulename.endswith('.py')
        modulename = modulename[:-3]

        # if module ends with '.__init__' strip that part off
        if modulename.endswith('.__init__'):
            modulename = modulename[:-9]

        modulenames.append(modulename)

    for modulename in sorted(modulenames):
        import_module(modulename)
