import abc
import enum
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Tuple,
    Union,
)

from paradox.interfaces import InvalidLogic, NotSupportedError, TypeMissing
from paradox.typing import (
    CrossAny,
    CrossBool,
    CrossCustomType,
    CrossDict,
    CrossList,
    CrossNull,
    CrossNum,
    CrossOmit,
    CrossOptional,
    CrossStr,
    CrossType,
    CrossUnion,
    FlexiType,
    unflex,
)

if TYPE_CHECKING:
    # XXX: flake8 doesn't realise we're using ellipsis below
    from builtins import ellipsis  # noqa: F401

Pannable = Union[
    str,
    int,
    bool,
    None,
    "ellipsis",
    "PanExpr",
    # TODO: this should be List[Pannable] but mypy doesn't support this yet
    List,
    Dict,
]


class PyPrecedence(enum.Enum):
    Literal = 1
    Dot = 2
    MultDiv = 3
    AddSub = 4


class TSPrecedence(enum.Enum):
    Literal = 1
    Dot = 2
    MultDiv = 3
    AddSub = 4


class PHPPrecedence(enum.Enum):
    Literal = 1
    Arrow = 2
    MultDiv = 3


def _phpstr(value: str) -> str:
    return "'{}'".format(value.replace("\\", "\\\\").replace("'", "\\'"))


def _wrapdot(pair: Tuple[str, Union[PyPrecedence, TSPrecedence, PHPPrecedence]]) -> str:
    code, prec = pair
    if isinstance(prec, PyPrecedence):
        if prec.value >= PyPrecedence.Dot.value:
            code = "(" + code + ")"
    elif isinstance(prec, TSPrecedence):
        if prec.value >= TSPrecedence.Dot.value:
            code = "(" + code + ")"
    else:
        assert isinstance(prec, PHPPrecedence)
        if prec.value >= PHPPrecedence.Arrow.value:
            code = "(" + code + ")"
    return code


def _wrapmult(pair: Tuple[str, Union[PyPrecedence, TSPrecedence, PHPPrecedence]]) -> str:
    code, prec = pair
    if isinstance(prec, PyPrecedence):
        if prec.value >= PyPrecedence.MultDiv.value:
            code = "(" + code + ")"
    elif isinstance(prec, TSPrecedence):
        if prec.value >= TSPrecedence.MultDiv.value:
            code = "(" + code + ")"
    else:
        assert isinstance(prec, PHPPrecedence)
        if prec.value >= PHPPrecedence.MultDiv.value:
            code = "(" + code + ")"
    return code


# TODO: this should implement paradox.interfaces.WantsImports
# TODO: each subclass of PanExpr() should recursively pull in imports from
# inner expressions as per test_nested_python_imports()
class PanExpr(abc.ABC):
    def cast(self, newtype: FlexiType) -> "PanCast":
        return PanCast(unflex(newtype), self)

    def lengthexpr(self) -> "PanLengthExpr":
        return PanLengthExpr(self)

    def isnullexpr(self) -> "PanExpr":
        return PanIsNullExpr(self)

    def getNegated(self) -> "PanExpr":
        raise NotImplementedError()

    def __getitem__(self, idx: Union[int, str]) -> "Union[PanIndexAccess, PanKeyAccess]":
        return self.getitem(idx)

    def getitem(
        self,
        idx: "Union[int, str, PanExpr]",
        fallback: "PanExpr" = None,
    ) -> "Union[PanIndexAccess, PanKeyAccess]":
        if isinstance(idx, PanExpr):
            if isinstance(self.getPanType(), CrossList):
                return PanIndexAccess(self, idx)
            return PanKeyAccess(self, idx)

        if isinstance(idx, int):
            assert idx == 0
            assert isinstance(self.getPanType(), CrossList)
            # TODO: check type of fallback if it is present
            return PanIndexAccess(self, idx, fallback)

        assert isinstance(idx, str)
        selftype = self.getPanType()
        assert isinstance(selftype, CrossDict) or isinstance(selftype, CrossAny)
        # TODO: check type of fallback if it is present
        return PanKeyAccess(self, idx, fallback)

    def getindex(
        self,
        idx: "Union[int, PanExpr]",
        fallback: "PanExpr" = None,
    ) -> "PanIndexAccess":
        selftype = self.getPanType()
        if not _could_by_a_list(selftype):
            raise InvalidLogic(f"Can't use getindex() on expr of type {selftype}")
        # TODO: check type of fallback if it is present
        return PanIndexAccess(self, idx, fallback)

    @abc.abstractmethod
    def getPanType(self) -> CrossType:
        """Return a CrossType representing the type of the expression.

        Raises TypeMissing if the PanExpr is missing type information."""

    @abc.abstractmethod
    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        """
        Get a string containing a python expression representing the PanExpr.

        The 2nd returned item is a PyPrecedence indicating the expressions precedence level. If you
        are trying to make an expression from two other expressions you may need to wrap one in
        parenthesis if the PyPrecedence is too high.
        """

    @abc.abstractmethod
    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        """
        Get the TS Type string for this CrossType.

        The 2nd return value is a boolean indicating whether the type string is "self-contained"
        enough that it can be combined with a suffix like "[]" to indicate it is an array of
        things.
        """

    @abc.abstractmethod
    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        """
        Get a string containing a PHP expression representing the PanExpr.

        The 2nd returned item is a PHPPrecedence indicating the expressions precedence level. If
        you are trying to make an expression from two other expressions you may need to wrap one in
        parenthesis if the PHPPrecedence is too high.
        """

    def getprop(self, propname: str, type: FlexiType = None) -> "PanProp":
        if type is None:
            type = CrossAny()
        else:
            type = unflex(type)
        return PanProp(propname, type, self)


class PanLiteral(PanExpr):
    def __init__(self, val: Union[int, str, bool, None]) -> None:
        self._val = val

    def getPanType(self) -> CrossType:
        # XXX: isinstance(..., bool) must come before isinstance(..., int) because a bool is also
        # an int in python!
        if isinstance(self._val, bool):
            return CrossBool()
        if isinstance(self._val, int):
            return CrossNum()
        if isinstance(self._val, str):
            return CrossStr()
        assert self._val is None
        return CrossNull()

    def isstr(self) -> bool:
        return isinstance(self._val, str)

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        return repr(self._val), PyPrecedence.Literal

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        if self._val is None:
            return "null", TSPrecedence.Literal
        if self._val is True:
            return "true", TSPrecedence.Literal
        if self._val is False:
            return "false", TSPrecedence.Literal
        return repr(self._val), TSPrecedence.Literal

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        if self._val is None:
            return "null", PHPPrecedence.Literal
        if isinstance(self._val, bool):
            return ("true" if self._val else "false"), PHPPrecedence.Literal
        if isinstance(self._val, int):
            return repr(self._val), PHPPrecedence.Literal
        assert isinstance(self._val, str)
        return _phpstr(self._val), PHPPrecedence.Literal

    def getRawStr(self) -> str:
        assert isinstance(self._val, str)
        return self._val


class PanIsType(PanExpr):
    def __init__(
        self,
        expr: PanExpr,
        expected: Literal["str", "int", "bool", "list", "dict"],
    ) -> None:
        self._expr = expr
        self._expected = expected

    def getPanType(self) -> CrossBool:
        return CrossBool()

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        types_ = {
            "str": "str",
            "int": "int",
            "bool": "bool",
            "list": "list",
            "dict": "dict",
        }
        expr = self._expr.getPyExpr()[0]
        return f"isinstance({expr}, {types_[self._expected]})", PyPrecedence.Dot

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        raise Exception("TODO: finish this")  # noqa

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        functions = {
            "str": "is_string",
            "int": "is_int",
            "bool": "is_bool",
            "list": "is_array",
            "dict": "is_array",
        }

        code = functions[self._expected] + "(" + self._expr.getPHPExpr()[0] + ")"
        return code, PHPPrecedence.Arrow


class PanOmit(PanExpr):
    def getPanType(self) -> CrossType:
        return CrossOmit()

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        return "...", PyPrecedence.MultDiv

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        return "undefined", TSPrecedence.Literal

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        raise NotSupportedError("PHP has no way to express omitted arguments")


class PanList(PanExpr):
    def __init__(self, values: List[PanExpr], innertype: CrossType) -> None:
        super().__init__()

        self._values: List[PanExpr] = list(values)
        self._innertype = innertype

    def getPanType(self) -> CrossType:
        return CrossList(self._innertype)

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        items = [v.getPyExpr()[0] for v in self._values]
        return "[" + ", ".join(items) + "]", PyPrecedence.Literal

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        items = [v.getTSExpr()[0] for v in self._values]
        return "[" + ", ".join(items) + "]", TSPrecedence.Literal

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        items = [v.getPHPExpr()[0] for v in self._values]
        return "[" + ", ".join(items) + "]", PHPPrecedence.Literal

    def panAppend(self, extra: PanExpr) -> None:
        self._values.append(extra)


class PanDict(PanExpr):
    def __init__(
        self,
        pairs: Dict[str, PanExpr],
        keytype: CrossType,
        valuetype: CrossType,
    ) -> None:
        super().__init__()

        assert isinstance(keytype, CrossStr), "PanDict currently only accepts str keys"

        self._pairs: Dict[str, PanExpr] = {k: v for k, v in pairs.items()}
        self._valuetype = valuetype

    def getPanType(self) -> CrossType:
        return CrossDict(CrossStr(), self._valuetype)

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        inner = [f"{k!r}: {v.getPyExpr()[0]}" for k, v in self._pairs.items()]
        code = "{" + ", ".join(inner) + "}"
        return code, PyPrecedence.Literal

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        inner = [f"{k!r}: {v.getTSExpr()[0]}" for k, v in self._pairs.items()]
        code = "{" + ", ".join(inner) + "}"
        return code, TSPrecedence.Literal

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        inner = [_phpstr(k) + " => " + v.getPHPExpr()[0] for k, v in self._pairs.items()]
        code = "[" + ", ".join(inner) + "]"
        return code, PHPPrecedence.Literal

    def addPair(self, key: PanExpr, val: PanExpr) -> None:
        assert isinstance(key, PanLiteral), "PanDict currently only supports str keys"
        assert isinstance(key.getPanType(), CrossStr), "PanDict currently only supports str keys"
        realkey = key.getRawStr()
        assert realkey not in self._pairs
        self._pairs[realkey] = val


# TODO: this needs to import typing.cast()
class PanCast(PanExpr):
    def __init__(self, type: CrossType, expr: PanExpr) -> None:
        super().__init__()

        self._type = type
        self._expr = expr

    def getPanType(self) -> CrossType:
        return self._type

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        typeexpr = self._type.getQuotedPyType()
        valexpr = self._expr.getPyExpr()[0]
        return f"cast({typeexpr}, {valexpr})", PyPrecedence.MultDiv

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        typeexpr = self._type.getTSType()[0]
        valexpr, valprec = self._expr.getTSExpr()
        if valprec.value > TSPrecedence.Dot.value:
            valexpr = "(" + valexpr + ")"
        return f"({valexpr} as {typeexpr})", TSPrecedence.Literal

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        # TODO: finish this and add a unit test
        raise NotImplementedError("PanCast is not yet implemented in PHP")


class _PanItemAccess(PanExpr):
    _target: PanExpr
    _idx: Union[int, str, PanExpr]
    _fallback: Optional[PanExpr]

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        targetstr, targetprec = self._target.getPyExpr()
        if targetprec.value > PyPrecedence.Dot.value:
            targetstr = "(" + targetstr + ")"

        if isinstance(self._idx, PanExpr):
            indexexpr = self._idx.getPyExpr()[0]
        else:
            indexexpr = repr(self._idx)

        if self._fallback:
            return self._getPyExprWithFallback(targetstr, indexexpr, self._fallback)

        return targetstr + "[" + indexexpr + "]", PyPrecedence.Dot

    def _getPyExprWithFallback(
        self,
        targetstr: str,
        indexstr: str,
        fallbackexpr: PanExpr,
    ) -> Tuple[str, PyPrecedence]:
        raise NotImplementedError()

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        targetstr, targetprec = self._target.getTSExpr()
        if targetprec.value > TSPrecedence.Dot.value:
            targetstr = "(" + targetstr + ")"

        if isinstance(self._idx, PanExpr):
            indexexpr = self._idx.getTSExpr()[0]
        else:
            indexexpr = repr(self._idx)

        if self._fallback:
            return self._getTSExprWithFallback(targetstr, indexexpr, self._fallback)

        return targetstr + "[" + indexexpr + "]", TSPrecedence.Dot

    def _getTSExprWithFallback(
        self,
        targetstr: str,
        indexstr: str,
        fallbackexpr: PanExpr,
    ) -> Tuple[str, TSPrecedence]:
        raise NotImplementedError()

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        targetstr, targetprec = self._target.getPHPExpr()
        if targetprec.value > PHPPrecedence.Arrow.value:
            targetstr = "(" + targetstr + ")"

        if isinstance(self._idx, PanExpr):
            indexexpr = self._idx.getPHPExpr()[0]
        elif isinstance(self._idx, int):
            indexexpr = repr(self._idx)
        else:
            indexexpr = _phpstr(self._idx)

        precedence = PHPPrecedence.Arrow
        phpexpr = targetstr + "[" + indexexpr + "]"

        if self._fallback:
            phpexpr += " ?? " + _wrapmult(self._fallback.getPHPExpr())
            precedence = PHPPrecedence.MultDiv

        return phpexpr, precedence


class PanIndexAccess(_PanItemAccess):
    def __init__(
        self,
        target: PanExpr,
        idx: Union[int, PanExpr],
        fallback: PanExpr = None,
    ) -> None:
        super().__init__()

        self._target = target
        self._idx = idx
        self._fallback = fallback

    def getPanType(self) -> CrossType:
        targettype = self._target.getPanType()
        if isinstance(targettype, CrossAny):
            return CrossAny()
        assert isinstance(targettype, CrossList)
        return targettype.getWrappedType()

    def _getPyExprWithFallback(
        self,
        targetstr: str,
        indexstr: str,
        fallbackexpr: PanExpr,
    ) -> Tuple[str, PyPrecedence]:
        # TODO: for a python iterable you can use this formula:
        #   next(itertools.islice(z, 2, None), fallback)
        # See https://docs.python.org/3/library/itertools.html#itertools-recipes
        raise Exception("TODO: handle fallback")


class PanKeyAccess(_PanItemAccess):
    def __init__(
        self,
        target: PanExpr,
        key: Union[str, PanExpr],
        # WARNING: the fallback is not guaranteed lazy-evaluated in all
        # generated languages
        fallback: PanExpr = None,
    ) -> None:
        super().__init__()

        self._target = target
        self._idx = key
        self._fallback = fallback

    def _getPyExprWithFallback(
        self,
        targetstr: str,
        indexstr: str,
        fallbackexpr: PanExpr,
    ) -> Tuple[str, PyPrecedence]:
        return (
            f"{targetstr}.get({indexstr}, {fallbackexpr.getPyExpr()[0]})",
            PyPrecedence.Dot,
        )

    def _getTSExprWithFallback(
        self,
        targetstr: str,
        indexstr: str,
        fallbackexpr: PanExpr,
    ) -> Tuple[str, TSPrecedence]:
        accessstr = targetstr + "[" + indexstr + "]"
        return (
            f"{accessstr} === undefined ? {fallbackexpr.getTSExpr()[0]} : {accessstr}",
            TSPrecedence.Dot,
        )

    def getPanType(self) -> CrossType:
        targettype = self._target.getPanType()
        if isinstance(targettype, CrossAny):
            return CrossAny()
        assert isinstance(targettype, CrossDict)
        return targettype.getValueType()


class PanVar(PanExpr):
    def __init__(self, name: str, type: Optional[CrossType]) -> None:
        self._name = name
        self._type = type

    @property
    def rawname(self) -> str:
        return self._name

    def __repr__(self) -> str:
        t = ""
        if self._type:
            t = ": " + self._type.getPyType()[0]
        return f"<PanVar({self._name}{t})>"

    def getPanType(self) -> CrossType:
        if self._type is None:
            raise TypeMissing(f"PanVar {self._name} has no type")
        return self._type

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        return self._name, PyPrecedence.Literal

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        return self._name, TSPrecedence.Literal

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        return "$" + self._name, PHPPrecedence.Literal


class PanProp(PanVar):
    def __init__(self, name: str, type: CrossType, owner: Optional[PanExpr]) -> None:
        super().__init__(name, type)

        self._owner: Optional[PanExpr] = owner

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        if self._owner is None:
            return "self." + self._name, PyPrecedence.Dot
        ownerexpr, ownerprec = self._owner.getPyExpr()
        if ownerprec.value > PyPrecedence.Dot.value:
            ownerexpr = "(" + ownerexpr + ")"
        return ownerexpr + "." + self._name, PyPrecedence.Dot

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        if self._owner is None:
            return "this." + self._name, TSPrecedence.Dot
        ownerexpr, ownerprec = self._owner.getTSExpr()
        if ownerprec.value > TSPrecedence.Dot.value:
            ownerexpr = "(" + ownerexpr + ")"
        return ownerexpr + "." + self._name, TSPrecedence.Dot

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        if self._owner is None:
            return "$this->" + self._name, PHPPrecedence.Arrow
        ownerexpr, ownerprec = self._owner.getPHPExpr()
        if ownerprec.value > PHPPrecedence.Arrow.value:
            ownerexpr = "(" + ownerexpr + ")"
        return ownerexpr + "->" + self._name, PHPPrecedence.Arrow


class PanCall(PanExpr):
    _pargs: List[PanExpr]
    _kwargs: Dict[str, PanExpr]
    _is_class_constructor = False

    def __init__(
        self,
        target: Union[str, PanProp],
        *args: PanExpr,
        **kwargs: PanExpr,
    ) -> None:
        super().__init__()

        self._target = target
        self._pargs = list(args)
        self._kwargs = {k: v for k, v in kwargs.items()}
        assert all(v is not None for v in self._kwargs.values())

    @classmethod
    def callClassConstructor(
        class_,
        classname: str,
        *args: PanExpr,
        **kwargs: PanExpr,
    ) -> "PanCall":
        instance = PanCall(
            classname,
            *args,
            **kwargs,
        )
        instance._is_class_constructor = True
        return instance

    def addPositionalArg(self, expr: PanExpr) -> None:
        self._pargs.append(expr)

    def addKWArg(self, argname: str, expr: PanExpr) -> None:
        assert argname not in self._kwargs, f"Duplicate kwarg {argname!r}"
        assert expr is not None
        self._kwargs[argname] = expr

    def getPanType(self) -> CrossType:
        # TODO: implement this?
        raise NotImplementedError()

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        args = [a.getPyExpr()[0] for a in self._pargs]
        for k, v in self._kwargs.items():
            args.append(f"{k}={v.getPyExpr()[0]}")
        argstr = ", ".join(args)

        if isinstance(self._target, str):
            return f"{self._target}({argstr})", PyPrecedence.Dot

        target, targetprec = self._target.getPyExpr()
        if targetprec.value > PyPrecedence.Dot.value:
            target = "(" + target + ")"
        return target + "(" + argstr + ")", PyPrecedence.Dot

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        argstr = ", ".join(a.getTSExpr()[0] for a in self._pargs)
        assert not len(self._kwargs), "KWArgs not supported in TS"

        if isinstance(self._target, str):
            expr = f"{self._target}({argstr})"
            if self._is_class_constructor:
                expr = "new " + expr
            return expr, TSPrecedence.Dot

        assert not self._is_class_constructor
        target, targetprec = self._target.getTSExpr()
        if targetprec.value > TSPrecedence.Dot.value:
            target = "(" + target + ")"
        return target + "(" + argstr + ")", TSPrecedence.Dot

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        argstr = ", ".join(a.getPHPExpr()[0] for a in self._pargs)
        assert not len(self._kwargs), "KWArgs not supported in PHP"

        if isinstance(self._target, str):
            new = "new " if self._is_class_constructor else ""
            return f"{new}{self._target}({argstr})", PHPPrecedence.Arrow

        target, targetprec = self._target.getPHPExpr()
        if targetprec.value > PHPPrecedence.Arrow.value:
            target = "(" + target + ")"
        return target + "(" + argstr + ")", PHPPrecedence.Arrow


class PanStringBuilder(PanExpr):
    _parts: List[PanExpr]

    def __init__(
        self,
        parts: Iterable[PanExpr],
    ) -> None:
        super().__init__()

        self._parts = list(parts)

    def getPanType(self) -> CrossType:
        return CrossStr()

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        expr = 'f"'
        for p in self._parts:
            if isinstance(p, PanLiteral) and p.isstr():
                expr += repr(p.getRawStr())[1:-1].replace("{", "{{").replace("}", "}}")
            else:
                expr += "{"
                expr += p.getPyExpr()[0]
                expr += "}"
        expr += '"'
        return expr, PyPrecedence.Literal

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        expr = "`"
        for p in self._parts:
            if isinstance(p, PanLiteral) and p.isstr():
                expr += repr(p.getRawStr())[1:-1].replace("$", "\\$")
            else:
                expr += "${"
                expr += p.getTSExpr()[0]
                expr += "}"
        expr += "`"
        return expr, TSPrecedence.Literal

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        parts = []
        for p in self._parts:
            if isinstance(p, PanLiteral) and p.isstr():
                parts.append(_phpstr(p.getRawStr()))
            else:
                parts.append(_wrapmult(p.getPHPExpr()))
        return " . ".join(parts), PHPPrecedence.MultDiv


# TODO: remove this in favour of HardCodedExpr()
class PanTSOnly(PanExpr):
    def __init__(self, code: str, precedence: TSPrecedence = TSPrecedence.MultDiv) -> None:
        self._code = code
        self._prec = precedence

    def getPanType(self) -> CrossType:
        raise Exception("TODO: not implemented")

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        raise Exception("PanTSOnly is unable to produce a Python expression")

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        return self._code, self._prec

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        raise Exception("PanTSOnly is unable to produce a PHP expression")


# TODO: remove this in favour of HardCodedExpr()
class PanPyOnly(PanExpr):
    def __init__(self, code: str, precedence: PyPrecedence = PyPrecedence.MultDiv) -> None:
        self._code = code
        self._prec = precedence

    def getPanType(self) -> CrossType:
        raise Exception("TODO: not implemented")

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        return self._code, self._prec

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        raise Exception(f"PanPyOnly('{self._code}') is unable to produce a TS expression")

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        raise Exception(f"PanPyOnly('{self._code}') is unable to produce a PHP expression")


# TODO: remove this in favour of HardCodedExpr()
class PanPHPOnly(PanExpr):
    def __init__(self, code: str, precedence: PHPPrecedence = PHPPrecedence.MultDiv) -> None:
        self._code = code
        self._prec = precedence

    def getPanType(self) -> CrossType:
        raise Exception("TODO: not implemented")

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        raise Exception("PanPHPOnly is unable to produce a Python expression")

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        raise Exception("PanPyOnly is unable to produce a TS expression")

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        return self._code, self._prec


class PanAndOr(PanExpr):
    def __init__(self, operation: Literal["AND", "OR"], arguments: List[PanExpr]) -> None:
        super().__init__()

        self._operation = operation
        self._arguments = arguments

    def getPanType(self) -> CrossType:
        return CrossBool()

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        if len(self._arguments) == 1:
            return f"bool({self._arguments[0].getPyExpr()[0]})", PyPrecedence.Literal
        # NOTE: we wrap each expr in parenthesis to avoid potential precedence issues
        each = [f"({a.getPyExpr()[0]})" for a in self._arguments]
        join = " or " if self._operation == "OR" else " and "
        return f"bool({join.join(each)})", PyPrecedence.Literal

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        if len(self._arguments) == 1:
            return f"!!({self._arguments[0].getTSExpr()[0]})", TSPrecedence.AddSub
        # NOTE: we wrap each expr in parenthesis to avoid potential precedence issues
        each = [f"({a.getPyExpr()[0]})" for a in self._arguments]
        join = " || " if self._operation == "OR" else " && "
        return f"!!({join.join(each)})", TSPrecedence.Literal

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        # we want to wrap args that have precedence higher than ->
        args = [_wrapdot(arg.getPHPExpr()) for arg in self._arguments]

        if len(args) == 1:
            return "(bool)" + args[0], PHPPrecedence.MultDiv

        # NOTE: we wrap each expr in parenthesis to avoid potential precedence issues
        join = " || " if self._operation == "OR" else " && "
        return join.join(args), PHPPrecedence.MultDiv


class PanNot(PanExpr):
    def __init__(self, arg: PanExpr) -> None:
        super().__init__()

        self._arg = arg

    def getPanType(self) -> CrossType:
        return CrossBool()

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        try:
            neg = self._arg.getNegated()
        except NotImplementedError:
            pass
        else:
            return neg.getPyExpr()

        return "not " + _wrapmult(self._arg.getPyExpr()), PyPrecedence.MultDiv

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        try:
            neg = self._arg.getNegated()
        except NotImplementedError:
            pass
        else:
            return neg.getTSExpr()

        return "!" + _wrapmult(self._arg.getTSExpr()), TSPrecedence.MultDiv

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        try:
            neg = self._arg.getNegated()
        except NotImplementedError:
            pass
        else:
            return neg.getPHPExpr()

        return "!" + _wrapmult(self._arg.getPHPExpr()), PHPPrecedence.MultDiv


class PanLengthExpr(PanExpr):
    def __init__(self, target: PanExpr) -> None:
        super().__init__()

        self._target = target

    def getPanType(self) -> CrossType:
        return CrossNum()

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        return f"len({self._target.getPyExpr()[0]})", PyPrecedence.Literal

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        return _wrapdot(self._target.getTSExpr()) + ".length", TSPrecedence.Dot

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        inner = self._target.getPHPExpr()[0]
        return f"count({inner})", PHPPrecedence.Literal


class PanIsNullExpr(PanExpr):
    def __init__(self, target: PanExpr) -> None:
        super().__init__()

        self._target = target
        self._negated = False

    def getPanType(self) -> CrossType:
        return CrossBool()

    def getNegated(self) -> "PanIsNullExpr":
        ret = PanIsNullExpr(self._target)
        ret._negated = not self._negated
        return ret

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        comp = " is not None" if self._negated else " is None"
        return _wrapdot(self._target.getPyExpr()) + comp, PyPrecedence.AddSub

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        comp = " !== null" if self._negated else " === null"
        return _wrapdot(self._target.getTSExpr()) + comp, TSPrecedence.AddSub

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        comp = " !== null" if self._negated else " === null"
        return _wrapdot(self._target.getPHPExpr()) + comp, PHPPrecedence.MultDiv


class PanCompare(PanExpr):
    def __init__(self, operation: Literal["===", "<", ">"], arg1: PanExpr, arg2: PanExpr) -> None:
        super().__init__()

        self._operation = operation
        self._arg1 = arg1
        self._arg2 = arg2
        self._negated = False

    def getPanType(self) -> CrossType:
        return CrossBool()

    def getNegated(self) -> "PanCompare":
        ret = PanCompare(self._operation, self._arg1, self._arg2)
        ret._negated = not self._negated
        return ret

    def _getComp(self) -> str:
        if self._negated:
            comps = {
                "===": "!==",
                "<": ">=",
                ">": "<=",
            }
            return comps[self._operation]

        return self._operation

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        if self._operation == "===":
            # python doesn't have the "exactly equal" operator - its "==" operator does this.
            comp = "!=" if self._negated else "=="
        else:
            comp = self._getComp()
        _arg1 = _wrapmult(self._arg1.getPyExpr())
        _arg2 = _wrapmult(self._arg2.getPyExpr())
        return f"{_arg1} {comp} {_arg2}", PyPrecedence.MultDiv

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        comp = self._getComp()
        _arg1 = _wrapmult(self._arg1.getTSExpr())
        _arg2 = _wrapmult(self._arg2.getTSExpr())
        return f"{_arg1} {comp} {_arg2}", TSPrecedence.MultDiv

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        comp = self._getComp()
        _arg1 = _wrapmult(self._arg1.getPHPExpr())
        _arg2 = _wrapmult(self._arg2.getPHPExpr())
        return f"{_arg1} {comp} {_arg2}", PHPPrecedence.MultDiv


class PanAwait(PanExpr):
    def __init__(self, waitable: PanExpr) -> None:
        self._waitable: PanExpr = waitable

    def getPanType(self) -> CrossType:
        return self._waitable.getPanType()

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        inner = _wrapmult(self._waitable.getPyExpr())
        return "await " + inner, PyPrecedence.AddSub

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        inner = _wrapmult(self._waitable.getTSExpr())
        return "await " + inner, TSPrecedence.AddSub

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        raise NotSupportedError("PHP does not support await syntax")


class HardCodedExpr(PanExpr):
    def __init__(
        self,
        getphp: Callable[[], str] = None,
        getpy: Callable[[], str] = None,
        getts: Callable[[], str] = None,
        type: CrossType = None,
    ) -> None:
        self._getphp = getphp
        self._getpy = getpy
        self._getts = getts
        self._type = type

    def getPanType(self) -> CrossType:
        if self._type:
            return self._type
        raise TypeMissing("HardCodedExpr was not given a `type`")

    def getPyExpr(self) -> Tuple[str, PyPrecedence]:
        if not self._getpy:
            raise Exception("HardCodedExpr has no getpy() callback")
        return self._getpy(), PyPrecedence.MultDiv

    def getTSExpr(self) -> Tuple[str, TSPrecedence]:
        if not self._getts:
            raise Exception("HardCodedExpr has no getts() callback")
        return self._getts(), TSPrecedence.MultDiv

    def getPHPExpr(self) -> Tuple[str, PHPPrecedence]:
        if not self._getphp:
            raise Exception("HardCodedExpr has no getphp() callback")
        return self._getphp(), PHPPrecedence.MultDiv


# helpers
def pan(value: Pannable) -> PanExpr:
    if isinstance(value, PanExpr):
        # value is already good to go
        return value

    if isinstance(value, (int, str, bool)):
        return PanLiteral(value)

    if value is None:
        return PanLiteral(None)

    if value is ...:
        return PanOmit()

    if isinstance(value, list):
        return panlist(value)

    if isinstance(value, dict):
        return pandict(value)

    raise TypeError(f"Unexpected value {value!r}")


def panlist(values: Iterable[Pannable], innertype: CrossType = None) -> PanList:
    resolved: List[PanExpr] = [pan(v) for v in values]
    if innertype is None:
        assert len(resolved), "If no values are provided to panlist(), a type must be specified"
        innertype = resolved[0].getPanType()

    for v in resolved:
        # FIXME: ensure each item of `values` is compatible with innertype
        pass

    return PanList(resolved, innertype)


def pandict(pairs: Mapping[str, Pannable], valuetype: CrossType = None) -> PanDict:
    resolved: Dict[str, PanExpr] = {k: pan(v) for k, v in pairs.items()}
    if valuetype is None:
        assert len(resolved), "If no pairs are provided to pandict(), a type must be specified"
        valuetype = resolved[list(resolved.keys())[0]].getPanType()

    for k, v in resolved.items():
        # FIXME: ensure each item of `pairs` is compatible with innertype
        pass

    return PanDict(resolved, CrossStr(), valuetype)


def pyexpr(code: str, prec: PyPrecedence = PyPrecedence.MultDiv) -> PanPyOnly:
    return PanPyOnly(code, prec)


def phpexpr(code: str, prec: PHPPrecedence = PHPPrecedence.MultDiv) -> PanPHPOnly:
    return PanPHPOnly(code, prec)


def tsexpr(code: str, prec: TSPrecedence = TSPrecedence.MultDiv) -> PanTSOnly:
    return PanTSOnly(code, prec)


def pannotomit(expr: Pannable) -> PanExpr:
    return HardCodedExpr(
        getpy=lambda: f"not isinstance({pan(expr).getPyExpr()[0]}, type(...))",
        getts=lambda: f"typeof {_wrapdot(pan(expr).getPyExpr())} !== 'undefined'",
    )


def or_(*args: Pannable) -> PanAndOr:
    assert len(args)
    return PanAndOr("OR", [pan(a) for a in args])


def and_(*args: Pannable) -> PanAndOr:
    assert len(args)
    return PanAndOr("AND", [pan(a) for a in args])


def not_(arg: Pannable) -> PanNot:
    return PanNot(pan(arg))


def exacteq_(arg1: Pannable, arg2: Pannable) -> PanCompare:
    return PanCompare("===", pan(arg1), pan(arg2))


def isnull(arg: Pannable) -> PanExpr:
    return PanIsNullExpr(pan(arg))


def isbool(arg: Pannable) -> PanExpr:
    return PanIsType(pan(arg), "bool")


def isint(arg: Pannable) -> PanExpr:
    return PanIsType(pan(arg), "int")


def isstr(arg: Pannable) -> PanExpr:
    return PanIsType(pan(arg), "str")


def islist(arg: Pannable) -> PanExpr:
    return PanIsType(pan(arg), "list")


def isdict(arg: Pannable) -> PanExpr:
    return PanIsType(pan(arg), "dict")


def await_(awaitable: PanExpr) -> PanAwait:
    return PanAwait(awaitable)


def _could_by_a_list(t: CrossType) -> bool:
    if isinstance(t, CrossUnion):
        return any(_could_by_a_list(i) for i in t._inner)

    if isinstance(t, CrossOptional):
        return _could_by_a_list(t._inner)

    # have to treat CrossCustomType like Any here since we don't have any information on whether it
    # supports list index operations
    return isinstance(t, (CrossList, CrossAny, CrossCustomType))
