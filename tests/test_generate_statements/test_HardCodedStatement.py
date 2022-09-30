import builtins
from typing import Dict, Union

import pytest

from _paradoxtest import SupportedLang
from paradox.generate.statements import HardCodedStatement
from paradox.interfaces import ImplementationMissing
from paradox.output import Script


# test a HardCodedStatement that has most languages, but not all
def get_custom_statements() -> Dict[str, Union[str, None, "builtins.ellipsis"]]:
    return {
        "python": "print('hi there')",
        "php": "echo 'hi there';",
        "typescript": "console.log('hi there');",
    }


@pytest.mark.parametrize("send_ellipsis", [True, False])
def test_HardCodedStatement(send_ellipsis: bool, LANG: SupportedLang) -> None:
    # test a HardCodedStatement that has most languages, but not all
    kwargs = get_custom_statements()

    # remove implementation for one lang, either by sending the ellipsis or by
    # omitting it from kwargs
    if send_ellipsis:
        kwargs[LANG] = ...
    else:
        kwargs.pop(LANG)

    s = Script()

    # test that we raise ImplementationMissing
    s.also(HardCodedStatement())
    with pytest.raises(
        ImplementationMissing, match="HardCodedStatement was not given "
    ):
        s.get_source_code(lang=LANG)


def test_HardCodedStatement_can_omit_each_lang(LANG: SupportedLang) -> None:
    # test a HardCodedStatement that has most languages, but not all
    stmts = get_custom_statements()

    # set one lang to be omitted
    stmts[LANG] = None

    s = Script()

    s.also(HardCodedStatement(**stmts))

    expected_php = "<?php\n\necho 'hi there';\n"
    expected_python = "print('hi there')\n"
    expected_typescript = "console.log('hi there');\n"

    if LANG == "php":
        expected_php = "<?php\n\n"
    elif LANG == "python":
        expected_python = ""
    else:
        assert LANG == "typescript"
        expected_typescript = ""

    assert s.get_source_code(lang="php") == expected_php
    assert s.get_source_code(lang="python") == expected_python
    assert s.get_source_code(lang="typescript") == expected_typescript
