from textwrap import dedent

import pytest

from _paradoxtest import SupportedLang
from paradox.generate.statements import InterfaceSpec
from paradox.interfaces import NotSupportedError
from paradox.output import Script
from paradox.typing import CrossBool


def test_generate_interface_spec(LANG: SupportedLang) -> None:
    script = Script()
    spec = script.also(InterfaceSpec("Window"))
    spec.addProperty("closed", CrossBool())

    # Note that InterfaceSpec doesn't yet support methods

    # this will probably never be implemented for Python, isn't currently supported for PHP
    if LANG == "python":
        with pytest.raises(NotSupportedError):
            script.get_source_code(lang=LANG)
        return

    if LANG == "php":
        # Note that PHP doesn't support properties in interfaces
        expected = dedent(
            """
            <?php

            interface Window {
            }
            """
        ).lstrip()
    else:
        assert LANG == "typescript"
        expected = dedent(
            """
            interface Window {
                closed: boolean;
            }
            """
        ).lstrip()
    assert script.get_source_code(lang=LANG) == expected
