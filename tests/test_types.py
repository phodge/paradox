from typing import Any, Callable, Collection, Iterable, List, Optional

import pytest

from paradox.interfaces import (
    ImplementationMissing,
    ImportSpecPy,
    InvalidLogic,
    NotSupportedError,
)
from paradox.typing import (
    CrossAny,
    CrossBool,
    CrossCallable,
    CrossCustomType,
    CrossDict,
    CrossList,
    CrossLiteral,
    CrossMap,
    CrossNull,
    CrossNum,
    CrossOmit,
    CrossOptional,
    CrossSet,
    CrossStr,
    CrossType,
    CrossUnion,
    dictof,
    listof,
    lit,
    maybe,
    omittable,
    unflex,
    unionof,
)


def _assert_produced_types(
    t: CrossType,
    *,
    python: str,
    typescript: str,
    phplang: Optional[str],
    phpdoc: str,
) -> None:
    if phplang == "not_supported":
        assert phpdoc == "not_supported"
        # no way to support this in PHP
        with pytest.raises(NotSupportedError):
            t.getPHPTypes()
    else:
        assert t.getPHPTypes()[0] == phplang
        assert t.getPHPTypes()[1] == phpdoc
    assert t.getPyType()[0] == python
    assert t.getTSType()[0] == typescript


def _assert_match_each(collection: Collection[Any], *conditions: Callable[[Any], bool]) -> None:
    if len(conditions) != len(collection):
        raise AssertionError(
            f"Got {len(conditions)} conditions but collection had {len(collection)} items"
        )
    check_conditions = list(conditions)
    for item in collection:
        unused_conditions = []
        matched = False
        for cond in check_conditions:
            if matched:
                unused_conditions.append(cond)
            elif cond(item):
                matched = True
            else:
                unused_conditions.append(cond)
        if not matched:
            raise AssertionError(f"Item {item!r} did not match any conditions")
        check_conditions = unused_conditions
    assert len(check_conditions) == 0


def _sorted_imports(imports: Iterable[ImportSpecPy]) -> List[ImportSpecPy]:
    return sorted(set(imports), key=lambda i: (i[0], i[1] or ""))


def test_flat_CrossTypes() -> None:
    _assert_produced_types(
        CrossAny(),
        python="Any",
        typescript="any",
        phplang=None,
        phpdoc="mixed",
    )
    _assert_produced_types(
        CrossStr(),
        python="str",
        typescript="string",
        phplang="string",
        phpdoc="string",
    )
    _assert_produced_types(
        CrossNum(),
        python="int",
        typescript="number",
        phplang="int",
        phpdoc="int",
    )
    _assert_produced_types(
        CrossBool(),
        python="bool",
        typescript="boolean",
        phplang="bool",
        phpdoc="boolean",
    )
    _assert_produced_types(
        CrossNull(),
        python="None",
        typescript="null",
        phplang=None,
        phpdoc="null",
    )
    _assert_produced_types(
        CrossOmit(),
        python="builtins.ellipsis",
        typescript="undefined",
        phplang="not_supported",
        phpdoc="not_supported",
    )


def test_CrossList() -> None:
    _assert_produced_types(
        CrossList(CrossNum()),
        python="List[int]",
        typescript="number[]",
        phplang="array",
        phpdoc="int[]",
    )
    _assert_produced_types(
        CrossList(CrossList(CrossStr())),
        python="List[List[str]]",
        # verify that list of something complex changes to the Array<> syntax
        typescript="Array<string[]>",
        phplang="array",
        # test that list of something complex changes to just 'mixed'
        phpdoc="mixed",
    )
    assert isinstance(CrossList(CrossStr()).getWrappedType(), CrossStr)


def test_CrossUnion() -> None:
    _assert_produced_types(
        CrossUnion([CrossStr(), CrossNum()]),
        python="Union[str, int]",
        typescript="string | number",
        phplang=None,
        phpdoc="string|int",
    )
    _assert_produced_types(
        CrossUnion([CrossList(CrossStr()), CrossLiteral(["yes", "no", -1])]),
        python="Union[List[str], Literal[-1, 'no', 'yes']]",
        typescript="string[] | -1 | 'no' | 'yes'",
        phplang=None,
        phpdoc="string[]|int|string",
    )

    # test .alsoWith()
    union1 = CrossUnion([CrossStr(), CrossBool()])
    assert union1.getPyType()[0] == "Union[str, bool]"
    union2 = union1.alsoWith(CrossNull())
    assert union2.getPyType()[0] == "Union[str, bool, None]"

    # test .hasOmittable()
    assert not union2.hasOmittable()
    union3 = union2.alsoWith(CrossOmit())
    assert union3.getPyType()[0] == "Union[str, bool, None, builtins.ellipsis]"
    assert union3.hasOmittable()


def test_CrossDict_CrossMap() -> None:
    _assert_produced_types(
        CrossDict(CrossStr(), CrossNum()),
        python="Dict[str, int]",
        typescript="{[k: string]: number}",
        # hell yeah PHP
        phplang="array",
        phpdoc="int[]",
    )
    _assert_produced_types(
        CrossDict(CrossStr(), CrossOptional(CrossList(CrossNum()))),
        python="Dict[str, Optional[List[int]]]",
        typescript="{[k: string]: number[] | null}",
        phplang="array",
        phpdoc="mixed",
    )
    _assert_produced_types(
        CrossMap(CrossStr(), CrossNum()),
        python="Mapping[str, int]",
        typescript="Map<string, number>",
        phplang="Ds\\Map",
        phpdoc="Ds\\Map",
    )
    _assert_produced_types(
        CrossMap(CrossStr(), CrossOptional(CrossList(CrossNum()))),
        python="Mapping[str, Optional[List[int]]]",
        typescript="Map<string, number[] | null>",
        phplang="Ds\\Map",
        phpdoc="Ds\\Map",
    )
    dict1 = CrossDict(CrossNum(), CrossStr())
    assert isinstance(dict1.getKeyType(), CrossNum)
    assert isinstance(dict1.getValueType(), CrossStr)

    map1 = CrossMap(CrossNum(), CrossStr())
    assert isinstance(map1.getKeyType(), CrossNum)
    assert isinstance(map1.getValueType(), CrossStr)


def test_CrossOptional() -> None:
    _assert_produced_types(
        CrossOptional(CrossStr()),
        python="Optional[str]",
        typescript="string | null",
        phplang=None,
        phpdoc="null|string",
    )
    _assert_produced_types(
        CrossOptional(listof(int)),
        python="Optional[List[int]]",
        typescript="number[] | null",
        phplang=None,
        phpdoc="null|int[]",
    )
    expanded = CrossOptional(CrossNum()).expandWith(CrossStr(), CrossBool())
    assert isinstance(expanded, CrossUnion)
    _assert_match_each(
        expanded._inner,
        lambda t: isinstance(t, CrossNum),
        lambda t: isinstance(t, CrossStr),
        lambda t: isinstance(t, CrossNull),
        lambda t: isinstance(t, CrossBool),
    )


def test_CrossLiteral() -> None:
    # NOTE: this next assertion also verifies two important things about CrossLiteral:
    # - Literals are written out in predictable order
    # - Literals can contain 1 and True at the same time
    _assert_produced_types(
        CrossLiteral([2, "b", False, "a", 1, True]),
        python="Literal[True, False, 1, 2, 'a', 'b']",
        typescript="true | false | 1 | 2 | 'a' | 'b'",
        phplang="mixed",
        phpdoc="bool|int|string",
    )


def test_CrossSet() -> None:
    _assert_produced_types(
        CrossSet(CrossStr()),
        python="Set[str]",
        typescript="Set<string>",
        phplang="not_supported",
        phpdoc="not_supported",
    )
    assert isinstance(CrossSet(CrossStr()).getWrappedType(), CrossStr)


def test_CrossCustomType() -> None:
    t = CrossCustomType(
        python="List[Column[int]]",
        phplang="array",
        phpdoc="Column[]",
        typescript="Array<Column<number>>",
    )
    assert t.getPyType()[0] == "List[Column[int]]"
    assert t.getPHPTypes()[0] == "array"
    assert t.getPHPTypes()[1] == "Column[]"
    assert t.getTSType()[0] == "Array<Column<number>>"

    t.alsoImportPy("foo", ["Bar", "Baz"])
    t.alsoImportPy("typing_extensions")
    assert _sorted_imports(t.getPyImports()) == [
        ("foo", "Bar"),
        ("foo", "Baz"),
        ("typing_extensions", None),
    ]

    # test that we raise a NotImplementedError for each lang that isn't provided
    c1 = CrossCustomType(typescript="z")
    c1.getTSType()  # no error
    with pytest.raises(ImplementationMissing, match="Python implementation"):
        c1.getPyType()

    # sending Ellipsis here for phplang/phpdoc is equivalent to omitting the args (as we do for
    # typescript)
    c2 = CrossCustomType(python="z", phplang=..., phpdoc=...)
    c2.getPyType()  # no error
    with pytest.raises(ImplementationMissing, match="TypeScript implementation"):
        c2.getTSType()
    with pytest.raises(ImplementationMissing, match="PHP implementation"):
        c2.getPHPTypes()

    with pytest.raises(InvalidLogic):
        CrossCustomType(phplang="z")
    with pytest.raises(InvalidLogic):
        CrossCustomType(phpdoc="z")


def test_CrossCallable() -> None:
    _assert_produced_types(
        CrossCallable([CrossStr(), CrossNum()], CrossBool()),
        python="Callable[[str, int], bool]",
        typescript="(a: string, b: number) => boolean",
        phplang=None,
        phpdoc="callable",
    )


def test_unflex_shortcuts() -> None:
    assert isinstance(unflex(str), CrossStr)
    assert isinstance(unflex(int), CrossNum)
    assert isinstance(unflex(bool), CrossBool)
    assert isinstance(unflex(None), CrossNull)
    assert isinstance(lit("cheese"), CrossLiteral)
    _assert_match_each(
        lit(5, 10, "yes", "no")._other,
        lambda v: v == "yes",
        lambda v: v == "no",
        lambda v: v == 5,
        lambda v: v == 10,
    )
    _assert_match_each(
        lit(True)._booleans,
        lambda v: v is True,
    )
    _assert_match_each(
        lit(False)._booleans,
        lambda v: v is False,
    )

    union1 = unionof(int, str)
    assert isinstance(union1, CrossUnion)
    _assert_match_each(
        union1._inner,
        lambda t: isinstance(t, CrossNum),
        lambda t: isinstance(t, CrossStr),
    )

    a = omittable(union1)
    assert isinstance(a, CrossUnion)
    _assert_match_each(
        a._inner,
        lambda t: isinstance(t, CrossNum),
        lambda t: isinstance(t, CrossStr),
        lambda t: isinstance(t, CrossOmit),
    )

    assert isinstance(maybe(str), CrossOptional)
    assert isinstance(maybe(str)._inner, CrossStr)
    assert isinstance(listof(int), CrossList)
    assert isinstance(listof(int)._wrapped, CrossNum)

    d = dictof(str, int)
    assert isinstance(d, CrossDict)
    assert isinstance(d.getKeyType(), CrossStr)
    assert isinstance(d.getValueType(), CrossNum)

    # verify that maybe(unionof(...)) doesn't wrap the union in CrossOptional
    u2: Any = maybe(union1)
    assert isinstance(u2, CrossUnion)
    _assert_match_each(
        u2._inner,
        lambda t: isinstance(t, CrossStr),
        lambda t: isinstance(t, CrossNum),
        lambda t: isinstance(t, CrossNull),
    )

    # verify that maybe(CrossOptional(T)) returns the same CrossOptional
    o1 = CrossOptional(CrossStr())
    assert maybe(o1) is o1


def test_correct_python_imports() -> None:
    assert list(CrossAny().getPyImports()) == [("typing", "Any")]
    assert list(CrossLiteral([1]).getPyImports()) == [("typing", "Literal")]
    assert list(CrossOmit().getPyImports()) == [("builtins", None)]
    assert list(CrossOptional(CrossStr()).getPyImports()) == [("typing", "Optional")]
    assert list(CrossList(CrossStr()).getPyImports()) == [("typing", "List")]
    assert list(CrossSet(CrossStr()).getPyImports()) == [("typing", "Set")]
    assert list(CrossUnion([CrossStr(), CrossNum()]).getPyImports()) == [("typing", "Union")]
    assert list(CrossDict(CrossStr(), CrossNum()).getPyImports()) == [("typing", "Dict")]
    assert list(CrossMap(CrossStr(), CrossNum()).getPyImports()) == [("typing", "Mapping")]
    assert list(CrossCallable([], CrossNull()).getPyImports()) == [("typing", "Callable")]


def test_nested_python_imports() -> None:
    # create a deeply nested structure incorporating each of the complex types, then make sure the
    # root CrossType returns the entire set of required python imports
    custom1 = CrossCustomType(python="Thing1")
    custom1.alsoImportPy("foo.bar", ["Thing1"])
    custom2 = CrossCustomType(python="Thing2")
    custom2.alsoImportPy("foo.bar", ["Thing2"])

    # deliberately import the whole module, as well as the M1 name
    custom3 = CrossCustomType(python="Union[M1, M2, some.module.M3]")
    custom3.alsoImportPy("some.module")
    custom3.alsoImportPy("some.module", ["M1", "M2"])

    custom4 = CrossCustomType(python="M4")
    custom4.alsoImportPy("monoliths", ["M4"])
    custom5 = CrossCustomType(python="M5")
    custom5.alsoImportPy("monoliths", ["M5"])

    d = CrossDict(custom2, CrossSet(CrossList(CrossOptional(custom1))))
    m = CrossMap(custom4, CrossUnion([d, custom3]))
    c = CrossCallable([d, m], custom5)
    assert _sorted_imports(c.getPyImports()) == [
        ("foo.bar", "Thing1"),
        ("foo.bar", "Thing2"),
        ("monoliths", "M4"),
        ("monoliths", "M5"),
        ("some.module", None),
        ("some.module", "M1"),
        ("some.module", "M2"),
        ("typing", "Callable"),
        ("typing", "Dict"),
        ("typing", "List"),
        ("typing", "Mapping"),
        ("typing", "Optional"),
        ("typing", "Set"),
        ("typing", "Union"),
    ]
