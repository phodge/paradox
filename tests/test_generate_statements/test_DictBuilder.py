from textwrap import dedent

import pytest

from _paradoxtest import SupportedLang
from paradox.expressions import PanVar
from paradox.generate.statements import DictBuilderStatement
from paradox.interfaces import NotSupportedError
from paradox.output import Script
from paradox.typing import dictof


@pytest.mark.parametrize("omit_some", [False, True])
def test_DictBuilder(LANG: SupportedLang, omit_some: bool) -> None:
    s = Script()

    b1 = s.also(DictBuilderStatement("my_dict", str, int))
    b1.addPair("one", False)
    b1.addPair("two", False)
    if omit_some:
        b1.addPair("three", True)
    b1.addPair("four", False)
    if omit_some:
        b1.addPair("five", True)

    if LANG == "php":
        expected = dedent(
            """
            <?php

            /** @var array */
            $my_dict = ['one' => $one, 'two' => $two, 'four' => $four];
            """
        ).lstrip()
        if omit_some:
            # currently PHP doesn't support omittable args
            with pytest.raises(NotSupportedError):
                s.get_source_code(lang=LANG)
            return
    elif LANG == "python":
        expected = dedent(
            """
            from typing import Dict

            my_dict: Dict[str, int] = {'one': one, 'two': two, 'four': four}
            """
        ).lstrip()
        if omit_some:
            expected += dedent(
                """
                if not isinstance(three, type(...)):
                    my_dict['three'] = three
                if not isinstance(five, type(...)):
                    my_dict['five'] = five
                """
            ).lstrip()
    else:
        assert LANG == "typescript"
        expected = dedent(
            """
            let my_dict: {[k: string]: number} = {'one': one, 'two': two, 'four': four};
            """
        ).lstrip()
        if omit_some:
            expected += dedent(
                """
                if (typeof three !== 'undefined') {
                    my_dict['three'] = three;
                }
                if (typeof five !== 'undefined') {
                    my_dict['five'] = five;
                }
                """
            ).lstrip()

    source_code = s.get_source_code(lang=LANG)
    assert source_code == expected


def test_DictBuilder_only_supports_str_keys(LANG: SupportedLang) -> None:
    # ok
    DictBuilderStatement("foo", str, int)

    # not allowed
    with pytest.raises(NotSupportedError, match="Only str keys"):
        DictBuilderStatement("foo", int, int)

    # also not allowed
    v_bar = PanVar("bar", dictof(int, int))
    with pytest.raises(NotSupportedError, match="Only str keys"):
        DictBuilderStatement.fromPanVar(v_bar)
