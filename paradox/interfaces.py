import abc
from contextlib import contextmanager
from typing import (
    TYPE_CHECKING,
    Iterable,
    Iterator,
    List,
    Literal,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

if TYPE_CHECKING:
    import builtins

    from paradox.expressions import (
        PanExpr,
        PanIndexAccess,
        PanKeyAccess,
        Pannable,
        PanVar,
    )
    from paradox.generate.statements import (
        ConditionalBlock,
        DictLoopBlock,
        ForLoopBlock,
        Statement,
        TryCatchBlock,
    )
    from paradox.typing import FlexiType


class NotSupportedError(NotImplementedError):
    """When you attempt to use a feature that is not supported by the target language."""


class ImplementationMissing(Exception):
    """
    Raised by hard-coded statement or expression when requested language implementation is missing.
    """


class InvalidLogic(Exception):
    """Raised when statements/expressions construction is not valid."""


class TypeMissing(Exception):
    """Raised by PanExpr.getPanType() when there is no type information."""


AlsoParam = TypeVar("AlsoParam", bound="Union[Statement, PanExpr]")


class AcceptsStatements(abc.ABC):
    @abc.abstractmethod
    def also(self, stmt: AlsoParam) -> AlsoParam:
        ...

    @abc.abstractmethod
    def blank(self) -> None:
        ...

    @abc.abstractmethod
    def remark(self, text: str) -> None:
        ...

    @abc.abstractmethod
    def alsoImportPy(self, module: str, names: List[str] = None) -> None:
        ...

    @abc.abstractmethod
    def alsoImportTS(self, module: str, names: List[str] = None) -> None:
        ...

    @abc.abstractmethod
    def alsoAppend(self, list_: "Pannable", value: "Pannable") -> None:
        ...

    @abc.abstractmethod
    def alsoRaise(self, ctor: str = None, *, msg: str = None, expr: "PanExpr" = None) -> None:
        ...

    @abc.abstractmethod
    def alsoAssign(
        self,
        var: "Union[PanVar, PanIndexAccess, PanKeyAccess]",
        expr: "Pannable",
    ) -> None:
        ...

    @abc.abstractmethod
    def alsoDeclare(
        self,
        target: "Union[str, PanVar]",
        type: "Union[None, FlexiType, Literal['no_type']]",
        value: "Union[Pannable, builtins.ellipsis]" = ...,
    ) -> "PanVar":
        ...

    @abc.abstractmethod
    @contextmanager
    def withTryBlock(self) -> "Iterator[TryCatchBlock]":
        ...

    @abc.abstractmethod
    @contextmanager
    def withCond(self, expr: "PanExpr") -> "Iterator[ConditionalBlock]":
        ...

    @abc.abstractmethod
    @contextmanager
    def withFor(
        self,
        assign: "PanVar",
        expr: "Pannable",
    ) -> "Iterator[ForLoopBlock]":
        ...

    @abc.abstractmethod
    @contextmanager
    def withDictIter(
        self,
        v_dict: "PanExpr",
        v_val: "PanVar",
        v_key: "PanVar" = None,
    ) -> "Iterator[DictLoopBlock]":
        ...


ImportSpecPy = Tuple[str, Optional[str]]
ImportSpecTS = Tuple[str, Optional[List[str]]]
ImportSpecPHP = Tuple[str, Optional[str]]


class WantsImports(abc.ABC):
    @abc.abstractmethod
    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        # XXX: we need to return an iterable here so that subclasses can use
        #   yield from super().getImportsPy()
        return []

    @abc.abstractmethod
    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        # XXX: we need to return an iterable here so that subclasses can use
        #   yield from super().getImportsTS()
        return []

    @abc.abstractmethod
    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        # XXX: we need to return an iterable here so that subclasses can use
        #   yield from super().getImportsPHP()
        return []
