from pathlib import Path
from subprocess import PIPE, run
from tempfile import TemporaryDirectory

import pytest

from paradox.expressions import phpexpr


@pytest.mark.parametrize("outcome", ["normal", "exception1", "exception2"])
def test_generate_try_catch_php(outcome: str) -> None:
    from paradox.generate.files import FilePHP

    with TemporaryDirectory() as tmpdir:
        scriptpath = Path(tmpdir, "script.php")
        script = FilePHP(scriptpath)
        with script.contents.withTryBlock() as tryblock:
            if outcome == "exception1":
                tryblock.alsoRaise("RuntimeException", msg="some message")
            elif outcome == "exception2":
                tryblock.alsoRaise("LogicException", msg="some message")
            tryblock.also(phpexpr('echo "inside try block\\n"'))

            with tryblock.withCatchBlock2(None, phpclass="RuntimeException") as catchblock:
                catchblock.also(phpexpr('echo "got RuntimeException\\n"'))
            with tryblock.withCatchBlock2(None, phpclass="LogicException") as catchblock:
                catchblock.also(phpexpr('echo "got LogicException\\n"'))
            with tryblock.withFinallyBlock() as finallyblock:
                finallyblock.also(phpexpr('echo "END\\n"'))

        script.writefile()

        result = run(["php", scriptpath], stdout=PIPE, check=True, encoding="utf-8")

    if outcome == "exception1":
        assert result.stdout == "got RuntimeException\nEND\n"
    elif outcome == "exception2":
        assert result.stdout == "got LogicException\nEND\n"
    else:
        assert result.stdout == "inside try block\nEND\n"
