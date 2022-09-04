from textwrap import dedent

import pytest
from _paradoxtest import SupportedLang


def test_generate_interface_spec(LANG: SupportedLang) -> None:
    from paradox.generate.statements import InterfaceSpec
    from paradox.output import Script
    from paradox.typing import CrossBool

    script = Script()
    spec = script.also(InterfaceSpec('Window'))
    spec.addProperty('closed', CrossBool())

    # Note that InterfaceSpec doesn't yet support methods

    # this will probably never be implemented for Python, isn't currently supported for PHP
    if LANG in ('php', 'python'):
        with pytest.raises(NotImplementedError):
            script.get_source_code(lang=LANG)
        return

    assert LANG == 'typescript'
    generated = script.get_source_code(lang=LANG)

    assert generated == dedent(
            '''
            interface Window {
                closed: boolean;
            }
            '''
    ).lstrip()
