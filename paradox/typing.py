import abc
from collections import defaultdict
from typing import Dict, Iterator, List, Optional, Tuple, Type, Union


class CrossType(abc.ABC):
    # which python typing module imports are needed
    _pythonotherimports: Dict[str, List[Union[str, None]]]

    def __init__(self) -> None:
        self._pythonotherimports = defaultdict(list)

    def getPyImports(self) -> Iterator[Tuple[str, Optional[str]]]:
        for module, names in self._pythonotherimports.items():
            for maybename in names:
                yield module, maybename

    @abc.abstractmethod
    def getPyType(self) -> Tuple[str, bool]:
        """
        Get the Python Type string for this CrossType.

        The 2nd return value is a boolean indicating whether the type needs to be quoted. Anything
        that is conditionally imported based on the presence of typing.TYPE_CHECKING needs to be
        quoted. Some magic types like builtins.ellipsis also only work in quotes.
        """

    def getQuotedPyType(self) -> str:
        """Get the Python Type string for this CrossType, wrapped in quotes if needed."""
        typeexpr, quote = self.getPyType()
        assert isinstance(typeexpr, str)

        if quote:
            # use repr() to wrap the whole thing in quotes
            return repr(typeexpr)

        return typeexpr

    @abc.abstractmethod
    def getTSType(self) -> Tuple[str, bool]:
        """
        Get the TS Type string for this CrossType.

        The 2nd return value is a boolean indicating whether the type string is "self-contained"
        enough that it can be combined with a suffix like "[]" to indicate it is an array of
        things.
        """

    @abc.abstractmethod
    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        """
        Get the PHP Type strings for this CrossType.

        The first string is the PHP in-language type that can be used for argument types. E.g.

            function(array $n) ...

        The second string is the phpDocumentor type that can be used in phpDocumentor comments.
        E.g.:

            /** @param int[] $n */

        The 3rd return value is a boolean indicating whether the type string is "self-contained"
        enough that it can be combined with a suffix like "[]" to indicate it is an array of
        things.
        """


class CrossAny(CrossType):
    def __init__(self) -> None:
        super().__init__()

    def getPyType(self) -> Tuple[str, bool]:
        return "typing.Any", False

    def getTSType(self) -> Tuple[str, bool]:
        return "any", True

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        return None, "mixed", True


class CrossStr(CrossType):
    def __init__(self) -> None:
        super().__init__()

    def getTSType(self) -> Tuple[str, bool]:
        return "string", True

    def getPyType(self) -> Tuple[str, bool]:
        return "str", False

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        return "string", "string", True


class CrossNum(CrossType):
    def __init__(self) -> None:
        super().__init__()

    def getPyType(self) -> Tuple[str, bool]:
        return "int", False

    def getTSType(self) -> Tuple[str, bool]:
        return "number", True

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        return "int", "int", True


class CrossBool(CrossType):
    def __init__(self) -> None:
        super().__init__()

    def getPyType(self) -> Tuple[str, bool]:
        return "bool", False

    def getTSType(self) -> Tuple[str, bool]:
        return "boolean", True

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        return "bool", "boolean", True


class CrossNull(CrossType):
    def __init__(self) -> None:
        super().__init__()

    def getPyType(self) -> Tuple[str, bool]:
        return "None", False

    def getTSType(self) -> Tuple[str, bool]:
        return "null", False

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        return None, "null", True


class CrossLiteral(CrossType):
    def __init__(self, variants: List[Union[str, int, bool]]) -> None:
        super().__init__()

        # FIXME: we need to make sure typing_extensions is imported
        self._pythonotherimports['typing_extensions'].append(None)

        assert len(variants)
        self._variants: List[Union[str, int, bool]] = variants

    def getTSType(self) -> Tuple[str, bool]:
        each = []
        for val in self._variants:
            if isinstance(val, bool):
                each.append("true" if val else "false")
            elif isinstance(val, int):
                each.append(repr(val))
            else:
                assert isinstance(val, str)
                each.append(repr(val))
        return " | ".join(each), True

    def getPyType(self) -> Tuple[str, bool]:
        inner = map(repr, self._variants)
        return f"typing_extensions.Literal[{', '.join(inner)}]", False

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        # PHP doesn't have support for literals, so we just use vanilla types
        subtypes = set()
        for v in self._variants:
            if isinstance(v, str):
                subtypes.add('string')
            elif isinstance(v, int):
                subtypes.add('int')
            else:
                assert isinstance(v, bool)
                subtypes.add('bool')
        subtypes2 = list(sorted(subtypes))
        assert len(subtypes2)
        if len(subtypes2) == 1:
            return subtypes2[0], subtypes2[0], True

        return 'mixed', '|'.join(subtypes2), False


class CrossOmit(CrossType):
    """Represents the Type of an argument when it is omitted."""
    def __init__(self) -> None:
        super().__init__()

        # FIXME: we need to make sure 'builtins' module is imported
        self._pythonotherimports['builtins'].append(None)

    def getPyType(self) -> Tuple[str, bool]:
        return "builtins.ellipsis", True

    def getTSType(self) -> Tuple[str, bool]:
        return "undefined", False

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        raise NotImplementedError("CrossOmit is not supported by PHP")


class CrossNewType(CrossType):
    def __init__(self, typename: str, *, quoted: bool = False) -> None:
        super().__init__()

        self._quoted: bool = quoted
        self._typename: str = typename

    def getPyType(self) -> Tuple[str, bool]:
        return self._typename, self._quoted

    def getTSType(self) -> Tuple[str, bool]:
        return self._typename, True

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        # TODO: do we need to do something about namespaces here?
        return self._typename, self._typename, True


class CrossOptional(CrossType):
    def __init__(self, inner: CrossType) -> None:
        super().__init__()

        self._inner: CrossType = inner
        self._pythonotherimports['typing'].append(None)

    def expandWith(self, *other: CrossType) -> "CrossUnion":
        items = [self._inner, CrossNull()]
        items.extend(other)
        return CrossUnion(items)

    def getTSType(self) -> Tuple[str, bool]:
        return self._inner.getTSType()[0] + " | null", False

    def getPyType(self) -> Tuple[str, bool]:
        innertype, innerquote = self._inner.getPyType()
        return f"typing.Optional[{innertype}]", innerquote

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        innertype = self._inner.getPHPTypes()[1]

        # IIRC we have to put the null variant first to satisfy some php linters and/or formatters
        return None, 'null|' + innertype, False


class CrossList(CrossType):
    def __init__(self, wrapped: CrossType) -> None:
        super().__init__()

        self._wrapped: CrossType = wrapped

    def getPyImports(self) -> Iterator[Tuple[str, Optional[str]]]:
        yield from super().getPyImports()
        yield from self._wrapped.getPyImports()

    def getWrappedType(self) -> CrossType:
        return self._wrapped

    def getTSType(self) -> Tuple[str, bool]:
        inner, listable = self._wrapped.getTSType()

        if listable:
            return inner + "[]", False

        return f"Array<{inner}>", False

    def getPyType(self) -> Tuple[str, bool]:
        innertype, innerquote = self._wrapped.getPyType()
        return f"typing.List[{innertype}]", innerquote

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        _, innertype, canbearray = self._wrapped.getPHPTypes()
        return 'array', innertype + '[]' if canbearray else 'mixed', False


class CrossSet(CrossType):
    def __init__(self, wrapped: CrossType) -> None:
        super().__init__()

        self._wrapped: CrossType = wrapped

    def getPyImports(self) -> Iterator[Tuple[str, Optional[str]]]:
        yield from super().getPyImports()
        yield from self._wrapped.getPyImports()

    def getWrappedType(self) -> CrossType:
        return self._wrapped

    def getTSType(self) -> Tuple[str, bool]:
        return f"Set<{self._wrapped.getTSType()[0]}>", False

    def getPyType(self) -> Tuple[str, bool]:
        innertype, innerquote = self._wrapped.getPyType()
        return f"typing.Set[{innertype}]", innerquote

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        raise NotImplementedError("PHP has no Set type")


class CrossDict(CrossType):
    _pythondicttype = "Dict"

    def __init__(self, key: CrossType, val: CrossType) -> None:
        super().__init__()

        self._key: CrossType = key
        self._val: CrossType = val

    def getPyImports(self) -> Iterator[Tuple[str, Optional[str]]]:
        yield from super().getPyImports()
        yield from self._key.getPyImports()
        yield from self._val.getPyImports()

    def getKeyType(self) -> CrossType:
        return self._key

    def getValueType(self) -> CrossType:
        return self._val

    def getTSType(self) -> Tuple[str, bool]:
        return f"{{[k: {self._key.getTSType()[0]}]: {self._val.getTSType()[0]}}}", False

    def getPyType(self) -> Tuple[str, bool]:
        keytype, keyquote = self._key.getPyType()
        valtype, valquote = self._val.getPyType()
        return f"typing.{self._pythondicttype}[{keytype}, {valtype}]", keyquote or valquote

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        _, innertype, canbearray = self._val.getPHPTypes()
        return 'array', innertype + '[]' if canbearray else 'mixed', False


class CrossMap(CrossDict):
    _pythondicttype = "Mapping"

    def getTSType(self) -> Tuple[str, bool]:
        return f"Map<{self._key.getTSType()[0]}, {self._val.getTSType()[0]}>", False

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        return 'Ds\\Map', 'Ds\\Map', True


class CrossUnion(CrossType):
    def __init__(self, innertypes: List[CrossType]) -> None:
        super().__init__()

        self._inner = innertypes[:]

    def getPyImports(self) -> Iterator[Tuple[str, Optional[str]]]:
        yield from super().getPyImports()
        for inner in self._inner:
            yield from inner.getPyImports()

    def alsoWith(self, *other: CrossType) -> "CrossUnion":
        """Return a new CrossUnion that also includes `other`."""
        return CrossUnion(self._inner + list(other))

    def hasOmittable(self) -> bool:
        return any(isinstance(t, CrossOmit) for t in self._inner)

    def getTSType(self) -> Tuple[str, bool]:
        return " | ".join([t.getTSType()[0] for t in self._inner]), False

    def getPyType(self) -> Tuple[str, bool]:
        inner = []
        quote = False
        for t in self._inner:
            innertype, innerquote = t.getPyType()
            inner.append(innertype)
            if innerquote:
                quote = True
        return f"typing.Union[{', '.join(inner)}]", quote

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        inner = [
            t.getPHPTypes()[1]
            for t in self._inner
        ]
        return None, '|'.join(inner), False


class CrossCallable(CrossType):
    def __init__(self, args: List[CrossType], ret: CrossType) -> None:
        super().__init__()

        self._args = args[:]
        self._ret = ret

    def getPyImports(self) -> Iterator[Tuple[str, Optional[str]]]:
        yield from super().getPyImports()
        yield from self._ret.getPyImports()
        for arg in self._args:
            yield from arg.getPyImports()

    def getTSType(self) -> Tuple[str, bool]:
        # obviously we only support up to 52 arguments
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        if len(self._args) > len(chars):
            raise Exception(
                f"CrossCallable() implementation does not support more than {len(chars)} arguments"
            )
        argtypes = [f"{chars[i]}: {t.getTSType()[0]}" for i, t in enumerate(self._args)]
        return f"({', '.join(argtypes)}) => {self._ret.getTSType()[0]}", False

    def getPyType(self) -> Tuple[str, bool]:
        argtypes = []
        quote = False
        for t in self._args:
            argtype, argquote = t.getPyType()
            argtypes.append(argtype)
            if argquote:
                quote = True
        rettype, retquote = self._ret.getPyType()
        return f"typing.Callable[[{', '.join(argtypes)}], {rettype}]", quote or retquote

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        return None, 'callable', True


class CrossPythonOnlyType(CrossType):
    def __init__(
        self,
        typeexpr: str,
        *,
        quotetype: bool = False,
    ) -> None:
        super().__init__()

        self._typeexpr = typeexpr
        self._quotetype = quotetype

    def getTSType(self) -> Tuple[str, bool]:
        raise NotImplementedError("CrossPythonOnlyType has no TS equivalent")

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        raise NotImplementedError("CrossPythonOnlyType has no PHP equivalent")

    def getPyType(self) -> Tuple[str, bool]:
        return self._typeexpr, self._quotetype


class CrossTypeScriptOnlyType(CrossType):
    def __init__(self, typeexpr: str) -> None:
        super().__init__()

        self._typeexpr = typeexpr

    def getTSType(self) -> Tuple[str, bool]:
        return self._typeexpr, False

    def getPyType(self) -> Tuple[str, bool]:
        raise NotImplementedError("CrossTypeScriptOnlyType has no Python equivalent")

    def getPHPTypes(self) -> Tuple[Optional[str], str, bool]:
        raise NotImplementedError("CrossTypeScriptOnlyType has no PHP equivalent")


FlexiType = Union[CrossType, Type[str], Type[int], Type[bool]]


def unflex(t: Union[FlexiType, None], *, allownewtypes: bool = False) -> CrossType:
    if t is None:
        return CrossNull()
    if t is str:
        return CrossStr()
    if t is int:
        return CrossNum()
    if t is bool:
        return CrossBool()
    if isinstance(t, CrossType):
        return t

    # NewType
    assert t.__module__ == "typing", f"t ({t!r}) is not a NewType"
    return CrossNewType(t.__name__)


# shortcuts
# - list/dict/union/optional/omittable
def maybe(t: FlexiType) -> Union[CrossOptional, CrossUnion]:
    # if it's already an Optional type, return it as-is
    if isinstance(t, CrossOptional):
        return t

    # if it's a union, append None/null as one of the union options
    if isinstance(t, CrossUnion):
        return t.alsoWith(CrossNull())

    # anything else we wrap with Optional
    return CrossOptional(unflex(t))


def listof(innertype: FlexiType) -> CrossList:
    return CrossList(unflex(innertype))


def dictof(key: FlexiType, val: FlexiType) -> CrossDict:
    return CrossDict(unflex(key), unflex(val))


def unionof(*inner: Union[FlexiType, None]) -> CrossUnion:
    return CrossUnion([unflex(t) for t in inner])


def lit(*variants: Union[str, int, bool]) -> CrossLiteral:
    return CrossLiteral(list(variants))


def omittable(t: FlexiType) -> CrossUnion:
    # if it's already an Optional type, turn it into a Union which includes <omitted>
    if isinstance(t, CrossOptional):
        return t.expandWith(CrossOmit())

    # if it's a union, append undefined/ellipsis as one of the union options
    if isinstance(t, CrossUnion):
        return t.alsoWith(CrossOmit())

    # anything else we wrap with a Union
    return CrossUnion([unflex(t)] + [CrossOmit()])
