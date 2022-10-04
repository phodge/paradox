import pytest


def test_producing_python_types() -> None:
    from paradox.typing import (
        CrossAny,
        CrossCallable,
        CrossMap,
        CrossNewType,
        CrossPythonOnlyType,
        CrossSet,
        CrossTypeScriptOnlyType,
        dictof,
        listof,
        lit,
        maybe,
        omittable,
        unflex,
        unionof,
    )

    assert CrossAny().getPyType()[0] == "typing.Any"
    assert unflex(str).getPyType()[0] == "str"
    assert unflex(int).getPyType()[0] == "int"
    assert unflex(bool).getPyType()[0] == "bool"
    assert unflex(None).getPyType()[0] == "None"
    assert lit("cheese").getPyType()[0] == "typing.Literal['cheese']"
    assert omittable(int).getPyType()[0] == "typing.Union[int, builtins.ellipsis]"
    assert CrossNewType("Widget").getPyType()[0] == "Widget"
    assert maybe(str).getPyType()[0] == "typing.Optional[str]"
    assert listof(int).getPyType()[0] == "typing.List[int]"
    assert CrossSet(unflex(str)).getPyType()[0] == "typing.Set[str]"
    assert dictof(str, int).getPyType()[0] == "typing.Dict[str, int]"
    assert CrossMap(unflex(str), unflex(int)).getPyType()[0] == "typing.Mapping[str, int]"
    assert unionof(str, int).getPyType()[0] == "typing.Union[str, int]"
    c = CrossCallable([unflex(str), unflex(int)], unflex(bool))
    assert c.getPyType()[0] == "typing.Callable[[str, int], bool]"
    assert CrossPythonOnlyType("typing.Iterable[int]").getPyType()[0] == "typing.Iterable[int]"

    with pytest.raises(NotImplementedError):
        assert CrossTypeScriptOnlyType("Promise<ApiFailure>").getPyType()


def test_producing_typescript_types() -> None:
    from paradox.typing import (
        CrossAny,
        CrossCallable,
        CrossMap,
        CrossNewType,
        CrossPythonOnlyType,
        CrossSet,
        CrossTypeScriptOnlyType,
        dictof,
        listof,
        lit,
        maybe,
        omittable,
        unflex,
        unionof,
    )

    assert CrossAny().getTSType()[0] == "any"
    assert unflex(str).getTSType()[0] == "string"
    assert unflex(int).getTSType()[0] == "number"
    assert unflex(bool).getTSType()[0] == "boolean"
    assert unflex(None).getTSType()[0] == "null"
    assert lit("cheese").getTSType()[0] == "'cheese'"
    assert omittable(int).getTSType()[0] == "number | undefined"
    assert CrossNewType("Widget").getTSType()[0] == "Widget"
    assert maybe(str).getTSType()[0] == "string | null"
    assert listof(int).getTSType()[0] == "number[]"
    assert CrossSet(unflex(str)).getTSType()[0] == "Set<string>"
    assert dictof(str, int).getTSType()[0] == "{[k: string]: number}"
    assert CrossMap(unflex(str), unflex(int)).getTSType()[0] == "Map<string, number>"
    assert unionof(str, int).getTSType()[0] == "string | number"
    c = CrossCallable([unflex(str), unflex(int)], unflex(bool))
    assert c.getTSType()[0] == "(a: string, b: number) => boolean"

    with pytest.raises(NotImplementedError):
        assert CrossPythonOnlyType("typing.Iterable[int]").getTSType()

    promise = CrossTypeScriptOnlyType("Promise<string>")
    assert promise.getTSType()[0] == "Promise<string>"

    # test that list of something complex changes to the Array<> syntax
    assert listof(promise).getTSType()[0] == "Array<Promise<string>>"


def test_producing_php_types() -> None:
    from paradox.typing import (
        CrossAny,
        CrossCallable,
        CrossMap,
        CrossNewType,
        CrossPythonOnlyType,
        CrossSet,
        CrossTypeScriptOnlyType,
        dictof,
        listof,
        lit,
        maybe,
        omittable,
        unflex,
        unionof,
    )

    assert CrossAny().getPHPTypes()[0] is None
    assert CrossAny().getPHPTypes()[1] == "mixed"
    assert unflex(str).getPHPTypes()[0] == "string"
    assert unflex(str).getPHPTypes()[1] == "string"
    assert unflex(int).getPHPTypes()[0] == "int"
    assert unflex(int).getPHPTypes()[1] == "int"
    assert unflex(bool).getPHPTypes()[0] == "bool"
    assert unflex(bool).getPHPTypes()[1] == "boolean"
    assert unflex(None).getPHPTypes()[0] is None
    assert unflex(None).getPHPTypes()[1] == "null"
    assert lit("cheese").getPHPTypes()[0] == "string"
    assert lit("cheese").getPHPTypes()[1] == "string"

    with pytest.raises(NotImplementedError):
        # no way to support this in PHP
        assert omittable(int).getPHPTypes()

    assert CrossNewType("Widget").getPHPTypes()[0] == "Widget"
    assert CrossNewType("Widget").getPHPTypes()[1] == "Widget"
    assert maybe(str).getPHPTypes()[0] is None
    assert maybe(str).getPHPTypes()[1] == "null|string"
    assert listof(int).getPHPTypes()[0] == "array"
    assert listof(int).getPHPTypes()[1] == "int[]"

    with pytest.raises(NotImplementedError):
        # no way to support this in PHP
        assert CrossSet(unflex(str)).getPHPTypes()

    # hell yeah PHP
    assert dictof(str, int).getPHPTypes()[0] == "array"
    assert dictof(str, int).getPHPTypes()[1] == "int[]"

    assert CrossMap(unflex(str), unflex(int)).getPHPTypes()[0] == "Ds\\Map"
    assert CrossMap(unflex(str), unflex(int)).getPHPTypes()[1] == "Ds\\Map"
    assert unionof(str, int).getPHPTypes()[0] is None
    assert unionof(str, int).getPHPTypes()[1] == "string|int"
    c = CrossCallable([unflex(str), unflex(int)], unflex(bool))
    assert c.getPHPTypes()[0] is None
    assert c.getPHPTypes()[1] == "callable"

    with pytest.raises(NotImplementedError):
        assert CrossPythonOnlyType("typing.Iterable[int]").getPHPTypes()

    with pytest.raises(NotImplementedError):
        assert CrossTypeScriptOnlyType("Promise<string>").getPHPTypes()

    # test that list of something complex changes to just 'mixed'
    assert listof(listof(unflex(int))).getPHPTypes()[0] == "array"
    assert listof(listof(unflex(int))).getPHPTypes()[1] == "mixed"  # more PHP greatness
