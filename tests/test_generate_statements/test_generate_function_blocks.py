from textwrap import dedent

import pytest

from _paradoxtest import SupportedLang
from paradox.expressions import PanStringBuilder, exacteq_, not_, or_, pan
from paradox.interfaces import NotSupportedError
from paradox.output import Script
from paradox.typing import (
    CrossAny,
    CrossBool,
    CrossList,
    CrossLiteral,
    CrossNum,
    CrossStr,
    maybe,
    unionof,
)


def test_FunctionSpec(LANG: SupportedLang) -> None:
    from paradox.generate.statements import NO_DEFAULT, FunctionSpec

    s = Script()

    fn1 = s.also(
        FunctionSpec(
            "int_identity",
            CrossNum(),
            docstring=["Returns the given input", "Param `num`: an integer"],
        )
    )
    v_num = fn1.addPositionalArg("num", CrossNum())
    fn1.alsoReturn(v_num)

    fn2 = s.also(FunctionSpec("hello_world", CrossStr()))
    v_who = fn2.addPositionalArg("who", CrossStr(), default="world")
    fn2.alsoReturn(PanStringBuilder([pan("Hello, "), v_who, pan("!")]))

    # test default=None vs default=NO_DEFAULT
    fn3 = s.also(FunctionSpec("test_defaults", CrossAny()))
    fn3.addPositionalArg("required_int", int, default=NO_DEFAULT)
    fn3.addPositionalArg("maybe_int", maybe(int), default=None)

    source_code = s.get_source_code(lang=LANG)

    if LANG == "php":
        expected = """
            <?php

            /**
             * Returns the given input
             * Param `num`: an integer
             */
            function int_identity(
                int $num
            ): int {
                return $num;
            }
            function hello_world(
                string $who = 'world'
            ): string {
                return 'Hello, ' . $who . '!';
            }
            function test_defaults(
                int $required_int,
                $maybe_int = null
            ) {
            }
            """
    elif LANG == "python":
        expected = '''
            import typing


            def int_identity(
                num: int,
            ) -> int:
                """
                Returns the given input
                Param `num`: an integer
                """
                return num

            def hello_world(
                who: str = 'world',
            ) -> str:
                return f"Hello, {who}!"

            def test_defaults(
                required_int: int,
                maybe_int: typing.Optional[int] = None,
            ) -> typing.Any:
                pass
            '''
    else:
        assert LANG == "typescript"
        expected = """
            /**
             * Returns the given input
             * Param `num`: an integer
             */
            function int_identity(
                num: number,
            ): number {
                return num;
            }
            function hello_world(
                who: string = 'world',
            ): string {
                return `Hello, ${who}!`;
            }
            function test_defaults(
                required_int: number,
                maybe_int: number | null = null,
            ): any {
            }
            """
    assert source_code == dedent(expected).lstrip()


def test_FunctionSpec_omittable_args(LANG: SupportedLang) -> None:
    from paradox.generate.statements import FunctionSpec

    script = Script()

    # test with/without arg default
    fn = script.also(FunctionSpec("omittable", CrossBool()))
    v_a = fn.addPositionalArg("a", CrossBool(), allowomit=True)
    v_b = fn.addPositionalArg("b", CrossBool(), allowomit=True)
    fn.alsoReturn(or_(not_(exacteq_(v_a, ...)), not_(exacteq_(v_b, ...))))

    if LANG == "php":
        with pytest.raises(NotImplementedError, match="not supported by PHP"):
            script.get_source_code(lang="php")
        return

    if LANG == "python":
        expected = """
            import builtins


            def omittable(
                a: 'typing.Union[bool, builtins.ellipsis]' = ...,
                b: 'typing.Union[bool, builtins.ellipsis]' = ...,
            ) -> bool:
                return bool((a != (...)) or (b != (...)))
            """
    else:
        assert LANG == "typescript"
        expected = """
            function omittable(
                a: boolean | undefined = undefined,
                b: boolean | undefined = undefined,
            ): boolean {
                return !!((a != (...)) || (b != (...)));
            }
            """

    generated = script.get_source_code(lang=LANG, pretty=False)

    assert generated == dedent(expected).lstrip()


def test_FunctionSpec_kwargs(LANG: SupportedLang) -> None:
    from paradox.generate.statements import NO_DEFAULT, FunctionSpec

    script = Script()

    # mix positional with kwargs / test providing a default
    fn1 = script.also(FunctionSpec("some_kwargs", CrossBool()))
    v_p1 = fn1.addPositionalArg("p1", CrossBool())
    v_p2 = fn1.addPositionalArg("p2", CrossBool())
    v_k1 = fn1.addKWArg("k1", CrossNum())
    v_k2 = fn1.addKWArg("k2", CrossNum(), default=55)
    v_k3 = fn1.addKWArg("k3", CrossNum(), default=NO_DEFAULT)
    fn1.alsoReturn(or_(v_p1, v_p2, v_k1, v_k2, v_k3))

    # just kwargs / test nullable=True/False / test allowomit=True/False
    fn2 = script.also(FunctionSpec("more_kwargs", CrossBool()))
    v_k1 = fn2.addKWArg("k1", CrossList(CrossStr()), nullable=False, allowomit=False)
    v_k2 = fn2.addKWArg("k2", CrossList(CrossStr()), nullable=True, allowomit=False)
    v_k3 = fn2.addKWArg("k3", CrossList(CrossStr()), nullable=False, allowomit=True)
    v_k4 = fn2.addKWArg("k4", CrossList(CrossStr()), nullable=True, allowomit=True)
    fn2.alsoReturn(or_(v_k1, v_k2, v_k3, v_k4))

    if LANG in ("php", "typescript"):
        with pytest.raises(NotSupportedError, match="does not support kwargs"):
            script.get_source_code(lang=LANG)
        return

    if LANG == "python":
        expected = """
            import builtins
            import typing


            def some_kwargs(
                p1: bool,
                p2: bool,
                *,
                k1: int,
                k2: int = 55,
                k3: int,
            ) -> bool:
                return bool((p1) or (p2) or (k1) or (k2) or (k3))

            def more_kwargs(
                *,
                k1: typing.List[str],
                k2: typing.Optional[typing.List[str]],
                k3: 'typing.Union[typing.List[str], builtins.ellipsis]' = ...,
                k4: 'typing.Union[typing.List[str], None, builtins.ellipsis]' = ...,
            ) -> bool:
                return bool((k1) or (k2) or (k3) or (k4))
            """
    else:
        raise Exception(f"Unexpected LANG {LANG!r}")

    generated = script.get_source_code(lang=LANG, pretty=False)

    assert generated == dedent(expected).lstrip()


def test_FunctionSpec_overloads(LANG: SupportedLang) -> None:
    from paradox.generate.statements import FunctionSpec

    script = Script()

    # mix positional with kwargs / test providing a default
    fn = script.also(FunctionSpec("overfun", CrossBool()))
    v_a = fn.addPositionalArg("a", CrossBool())
    v_b = fn.addPositionalArg("b", unionof(str, int))
    fn.alsoReturn(or_(v_a, v_b))

    fn.addOverload(
        {"a": CrossLiteral([True]), "b": CrossStr()},
        CrossLiteral([True]),
    )
    fn.addOverload(
        {"a": CrossLiteral([False]), "b": CrossNum()},
        CrossLiteral([False]),
    )

    if LANG == "php":
        with pytest.raises(NotSupportedError, match="does not support overloads"):
            script.get_source_code(lang=LANG)
        return

    if LANG == "typescript":
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            script.get_source_code(lang=LANG)
        return

    if LANG == "python":
        expected = """
            import typing
            import typing_extensions


            @typing.overload
            def overfun(
                a: typing_extensions.Literal[True],
                b: str,
            ) -> typing_extensions.Literal[True]:
                ...

            @typing.overload
            def overfun(
                a: typing_extensions.Literal[False],
                b: int,
            ) -> typing_extensions.Literal[False]:
                ...

            def overfun(
                a: bool,
                b: typing.Union[str, int],
            ) -> bool:
                return bool((a) or (b))
            """
    else:
        raise Exception(f"Unexpected LANG {LANG!r}")

    generated = script.get_source_code(lang=LANG, pretty=False)

    assert generated == dedent(expected).lstrip()


# TODO: add unit tests for FunctionSpec with isasync=True
