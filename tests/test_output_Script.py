import io
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

import pytest

from _paradoxtest import SupportedLang
from paradox.expressions import PanCall, pan
from paradox.interfaces import InvalidLogic
from paradox.output import Script
from paradox.typing import maybe, unflex


def test_Script(LANG: SupportedLang) -> None:
    s = Script()

    # add some new types
    s.add_new_type("UserEmail", maybe(str))
    s.add_new_type("UserID", unflex(int), tsexport=True)

    s.add_file_comment("Intro1")
    s.add_file_comment("Intro2")
    s.add_file_comment("")
    s.add_file_comment("Intro3")
    with s.withCond(pan(True)) as cond:
        cond.also(PanCall("some_fn"))

    # NOTE: methods from the AcceptsStatements interface are tested elsewhere
    # in test_interface_AcceptStatements.py

    if LANG == "php":
        expected = """
            <?php

            // Intro1
            // Intro2
            //
            // Intro3

            if (true) {
              some_fn();
            }

        """
    elif LANG == "python":
        expected = '''
            """
            Intro1
            Intro2

            Intro3
            """
            from typing import NewType, Optional

            UserEmail = NewType('UserEmail', Optional[str])
            UserID = NewType('UserID', int)

            if True:
              some_fn()

        '''
    else:
        assert LANG == "typescript"
        expected = """
            // Intro1
            // Intro2
            //
            // Intro3
            type UserEmail = string | null & {readonly brand: unique symbol};
            export type UserID = number & {readonly brand: unique symbol};

            if (true) {
              some_fn();
            }

        """

    source = s.get_source_code(lang=LANG, indentstr="  ")
    assert source == dedent(expected).lstrip()

    fp = io.StringIO()
    s.write_to_handle(fp, lang=LANG, indentstr="  ")
    fp.seek(0)
    stream = fp.read()
    assert stream == dedent(expected).lstrip()

    with TemporaryDirectory() as tmpdir:
        ext = {
            "php": "php",
            "python": "py",
            "typescript": "ts",
        }
        scriptpath = Path(tmpdir) / f"playscript.{ext}"
        s.write_to_path(scriptpath, lang=LANG, indentstr="  ")
        written = scriptpath.read_text()
        assert written == dedent(expected).lstrip()


def test_cannot_add_same_new_type_twice() -> None:
    s = Script()

    s.add_new_type("some_type", unflex(str))
    with pytest.raises(InvalidLogic):
        s.add_new_type("some_type", unflex(str))
