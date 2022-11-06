import pytest

from paradox.expressions import (
    PanAwait,
    PanCall,
    PanCast,
    PanExpr,
    PanKeyAccess,
    PanLiteral,
    PanOmit,
    PanVar,
    pan,
)
from paradox.interfaces import NotSupportedError
from paradox.typing import CrossAny, CrossList, CrossOmit, CrossStr, listof

# TODO: add tests for each of the following
# - PanIsType
# - PanList
# - PanDict
# - PanIndexAccess
# - PanVar
# - PanProp
# - PanCall
# - PanStringBuilder
# - PanTSOnly
# - PanPyOnly
# - PanPHPOnly
# - PanAndOr
# - PanNot
# - PanLengthExpr
# - PanIsNullExpr
# - PanCompare
# - HardCodedExpr
# - pan()
# - panlist()
# - pandict()
# - pyexpr()
# - phpexpr()
# - tsexpr()
# - pannotomit()
# - or_()
# - and_()
# - not_()
# - exacteq_()
# - isnull()
# - isbool()
# - isint()
# - isstr()
# - islist()
# - isdict()


def test_PanLiteral() -> None:
    assert PanLiteral(True).getPHPExpr()[0] == "true"
    assert PanLiteral(True).getPyExpr()[0] == "True"
    assert PanLiteral(True).getTSExpr()[0] == "true"
    assert PanLiteral(False).getPHPExpr()[0] == "false"
    assert PanLiteral(False).getPyExpr()[0] == "False"
    assert PanLiteral(False).getTSExpr()[0] == "false"
    assert PanLiteral(0).getPHPExpr()[0] == "0"
    assert PanLiteral(0).getPyExpr()[0] == "0"
    assert PanLiteral(0).getTSExpr()[0] == "0"
    assert PanLiteral(1250).getPHPExpr()[0] == "1250"
    assert PanLiteral(1250).getPyExpr()[0] == "1250"
    assert PanLiteral(1250).getTSExpr()[0] == "1250"
    assert PanLiteral(-912343).getPHPExpr()[0] == "-912343"
    assert PanLiteral(-912343).getPyExpr()[0] == "-912343"
    assert PanLiteral(-912343).getTSExpr()[0] == "-912343"
    assert PanLiteral("").getPHPExpr()[0] == "''"
    assert PanLiteral("").getPyExpr()[0] == "''"
    assert PanLiteral("").getTSExpr()[0] == "''"
    assert PanLiteral("'").getPHPExpr()[0] == "'\\''"
    assert PanLiteral("'").getPyExpr()[0] == '"\'"'
    assert PanLiteral("'").getTSExpr()[0] == '"\'"'
    assert PanLiteral("0").getPHPExpr()[0] == "'0'"
    assert PanLiteral("0").getPyExpr()[0] == "'0'"
    assert PanLiteral("0").getTSExpr()[0] == "'0'"


def test_PanOmit() -> None:
    o = PanOmit()
    assert o.getPyExpr()[0] == "..."
    assert o.getTSExpr()[0] == "undefined"
    with pytest.raises(NotSupportedError):
        assert o.getPHPExpr()
    assert isinstance(o.getPanType(), CrossOmit)


def test_PanCast() -> None:
    assert PanCast(CrossStr(), pan(5)).getPyExpr()[0] == "cast(str, 5)"
    assert PanCast(CrossStr(), pan(5)).getTSExpr()[0] == "(5 as string)"
    # TODO: this is not yet implemented in PHP


def test_PanKeyAccess() -> None:
    v_foo = PanVar("foo", None)
    v_foo = PanVar("foo", None)
    e_prop = v_foo.getprop("bar", CrossAny())
    e_meth = PanCall(v_foo.getprop("meth", CrossAny()), pan(5), pan("cheese"))

    def assert_(e: PanExpr, *, php: str, python: str, typescript: str) -> None:
        assert e.getPHPExpr()[0] == php
        assert e.getPyExpr()[0] == python
        assert e.getTSExpr()[0] == typescript

    assert_(
        PanKeyAccess(v_foo, "aaa"),
        php="$foo['aaa']",
        python="foo['aaa']",
        typescript="foo['aaa']",
    )
    assert_(
        PanKeyAccess(e_prop, pan(99)),
        php="$foo->bar[99]",
        python="foo.bar[99]",
        typescript="foo.bar[99]",
    )
    assert_(
        PanKeyAccess(e_meth, pan(-5)),
        php="$foo->meth(5, 'cheese')[-5]",
        python="foo.meth(5, 'cheese')[-5]",
        typescript="foo.meth(5, 'cheese')[-5]",
    )

    # with fallback
    assert_(
        PanKeyAccess(v_foo, "k", pan(75)),
        php="$foo['k'] ?? 75",
        python="foo.get('k', 75)",
        typescript="foo['k'] === undefined ? 75 : foo['k']",
    )
    assert_(
        PanKeyAccess(e_prop, "k", pan("def")),
        php="$foo->bar['k'] ?? 'def'",
        python="foo.bar.get('k', 'def')",
        typescript="foo.bar['k'] === undefined ? 'def' : foo.bar['k']",
    )
    # NOTE: this is problematic if the target expression potentially contains side effects, because
    # we can't use constructs that check for the property first then retrieve it
    # TODO: add a mechanism to PanKeyAccess() where it can raise an InvalidLogic exception if you
    # use a fallback with a base expression that has potential side effects
    # with pytest.raises(InvalidLogic, match="side effects"):
    #     PanKeyAccess(e_meth, "k", pan(False)).getPyExpr()
    # with pytest.raises(InvalidLogic, match="side effects"):
    #     PanKeyAccess(e_meth, "k", pan(False)).getPHPExpr()
    # with pytest.raises(InvalidLogic, match="side effects"):
    #     PanKeyAccess(e_meth, "k", pan(False)).getTSExpr()


def test_PanAwait() -> None:
    # verify it generates the correct code for each language
    call1 = PanCall("some_func")
    v_foo = PanVar("foo", CrossAny())
    call2 = PanCall(v_foo.getprop("some_method"), pan(5))
    assert PanAwait(call1).getPyExpr()[0] == "await some_func()"
    assert PanAwait(call1).getTSExpr()[0] == "await some_func()"
    assert PanAwait(call2).getPyExpr()[0] == "await foo.some_method(5)"
    assert PanAwait(call2).getTSExpr()[0] == "await foo.some_method(5)"

    # verify not supported under PHP
    with pytest.raises(NotSupportedError, match="PHP does not support"):
        PanAwait(call1).getPHPExpr()

    # verify its getPanType() method works as expected
    v_bar = PanVar("bar", listof(str))
    waittype = PanAwait(v_bar).getPanType()
    assert isinstance(waittype, CrossList)
    assert isinstance(waittype._wrapped, CrossStr)
