from textwrap import dedent

from _paradoxtest import SupportedLang
from paradox.expressions import PanVar, not_, pan
from paradox.generate.statements import ListAppendStatement
from paradox.output import Script
from paradox.typing import CrossList, CrossStr, dictof, listof


def test_ListAppendStatement(LANG: SupportedLang) -> None:
    s = Script()

    v_list = s.alsoDeclare("some_list", CrossList(CrossStr()), pan(["first"]))
    s.also(ListAppendStatement(v_list, pan("Hello world")))

    s.also(
        ListAppendStatement(
            PanVar("foo", type=dictof(str, listof(int))).getitem("bar"), pan(12345)
        )
    )

    # test with a list expression that has very low operator precedence
    s.also(ListAppendStatement(not_(PanVar("z", type=None)), pan(True)))

    source_code = s.get_source_code(lang=LANG)

    if LANG == "php":
        expected = """
            <?php

            /** @var string[] */
            $some_list = ['first'];
            $some_list[] = 'Hello world';
            $foo['bar'][] = 12345;
            (!$z)[] = true;
            """
    elif LANG == "python":
        expected = """
            from typing import List

            some_list: List[str] = ['first']
            some_list.append('Hello world')
            foo['bar'].append(12345)
            (not z).append(True)
            """
    else:
        assert LANG == "typescript"
        expected = """
            let some_list: string[] = ['first'];
            some_list.push('Hello world');
            foo['bar'].push(12345);
            (!z).push(true);
            """
    assert source_code == dedent(expected).lstrip()
