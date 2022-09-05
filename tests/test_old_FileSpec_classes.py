from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import Iterator, Optional

import pytest


@pytest.fixture
def tmppath() -> Iterator[Path]:
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.parametrize('namespace', [None, 'Cool\\Code'])
def test_FilePHP_produces_php(tmppath: Path, namespace: Optional[str]) -> None:
    from paradox.expressions import PanCall, PanVar, pan
    from paradox.generate.files import FilePHP

    scriptname = tmppath / 'script.php'
    fp = FilePHP(scriptname, namespace=namespace)

    fp.filecomment("This is a test script")
    fp.filecomment("Use it for testing")

    with fp.contents.withCond(pan(False)) as cond:
        cond.also(PanCall('strlen', pan('')))
    fp.contents.alsoDeclare('z', int, PanCall('count', PanVar('GLOBALS', None)))

    fp.writefile()

    # NOTE: there is currently nothing that uses PHP imports, but if/when that's added we should
    # test they work with FilePHP

    # NOTE: comments in paradox.output.php.write_custom_types() states that PHP does not support
    # custom types

    linebreak = ''
    nsline = ''
    if namespace:
        linebreak = '\n'
        nsline = f'namespace {namespace};\n'
    assert scriptname.read_text() == dedent(
            f'''
            <?php

            // This is a test script
            // Use it for testing{linebreak}
            {nsline}
            if (False) {{
                strlen('');
            }}

            /** @var int */
            $z = count($GLOBALS);
            '''
    ).lstrip()

    assert fp.getfirstline() == '<?php\n'

    # NOTE: FilePHP.makepretty() was never implemented


def test_FilePython_produces_python(tmppath: Path) -> None:
    from paradox.expressions import PanCall, pan
    from paradox.generate.files import FilePython
    from paradox.typing import maybe

    scriptname = tmppath / 'script.py'
    fp = FilePython(scriptname)

    fp.filecomment("This is a test script")
    fp.filecomment("Use it for testing")

    with fp.contents.withCond(pan(False)) as cond:
        cond.also(PanCall('len', pan('')))

    fp.contents.alsoDeclare('z', maybe(int), PanCall('len', pan('five')))

    fp.writefile()

    assert scriptname.read_text() == dedent(
            '''
            """
            This is a test script
            Use it for testing
            """
            import typing

            if False:
                len('')

            z: typing.Optional[int] = len('five')
            '''
    ).lstrip()

    assert fp.getfirstline() == '"""\n'

    # TODO: test fp.makepretty() somehow


def test_FileTS_produces_typescript(tmppath: Path) -> None:
    from paradox.expressions import PanCall, PanList, pan
    from paradox.generate.files import FileTS
    from paradox.typing import CrossAny, CrossList, unflex

    scriptname = tmppath / 'script.ts'
    fp = FileTS(scriptname, npmroot=tmppath)

    fp.filecomment("This is a test script")
    fp.filecomment("Use it for testing")

    with fp.contents.withCond(pan(False)) as cond:
        cond.also(PanCall('alert', pan('hello, world')))

    fp.contents.alsoDeclare('z', CrossList(unflex(int)), PanList([pan(1770)], CrossAny()))

    fp.writefile()

    assert scriptname.read_text() == dedent(
            '''
            // This is a test script
            // Use it for testing
            if (False) {
                alert('hello, world');
            }

            let z: number[] = [1770];
            '''
    ).lstrip()

    assert fp.getfirstline() == '// This is a test script\n'

    # TODO: test fp.makepretty() somehow