import abc
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple, Union

from typing_extensions import Literal

if TYPE_CHECKING:
    import builtins

    from paradox.expressions import (PanExpr, PanIndexAccess, PanKeyAccess,
                                     Pannable, PanVar)
    from paradox.generate.statements import (ConditionalBlock, DictLoopBlock,
                                             ForLoopBlock, Statement,
                                             TryCatchBlock)
    from paradox.typing import CrossType, FlexiType


class AcceptsStatements(abc.ABC):
    @abc.abstractmethod
    def also(self, stmt: "Union[Statement, PanExpr]") -> None: ...

    @abc.abstractmethod
    def blank(self) -> None: ...

    @abc.abstractmethod
    def remark(self, text: str) -> None: ...

    @abc.abstractmethod
    def alsoImportPy(self, module: str, names: List[str] = None) -> None: ...

    @abc.abstractmethod
    def alsoImportTS(self, module: str, names: List[str] = None) -> None: ...

    @abc.abstractmethod
    def alsoAppend(self, list_: "Pannable", value: "Pannable") -> None: ...

    @abc.abstractmethod
    def alsoRaise(self, ctor: str = None, *, msg: str = None, expr: "PanExpr" = None) -> None: ...

    @abc.abstractmethod
    def alsoAssign(
        self,
        var: "Union[PanVar, PanIndexAccess, PanKeyAccess]",
        expr: "Pannable",
    ) -> None: ...

    @abc.abstractmethod
    def alsoDeclare(
        self,
        target: "Union[str, PanVar]",
        type: "Union[None, FlexiType, Literal['no_type']]",
        value: "Union[Pannable, builtins.ellipsis]" = ...,
    ) -> "PanVar": ...

    @abc.abstractmethod
    @contextmanager
    def withTryBlock(self) -> 'Iterable[TryCatchBlock]': ...

    @abc.abstractmethod
    @contextmanager
    def withCond(self, expr: "PanExpr") -> 'Iterable[ConditionalBlock]': ...

    @abc.abstractmethod
    @contextmanager
    def withFor(
        self,
        assign: "PanVar",
        expr: "Pannable",
    ) -> 'Iterable[ForLoopBlock]': ...

    @abc.abstractmethod
    @contextmanager
    def withDictIter(
        self,
        v_dict: "PanExpr",
        v_val: "PanVar",
        v_key: "PanVar" = None,
    ) -> 'Iterable[DictLoopBlock]': ...


ImportSpecPy = Tuple[str, Optional[List[str]]]
ImportSpecTS = Tuple[str, Optional[List[str]]]
ImportSpecPHP = Tuple[str, Optional[str]]


class WantsImports(abc.ABC):
    @abc.abstractmethod
    def getImportsPy(self) -> Iterable[ImportSpecPy]: ...

    @abc.abstractmethod
    def getImportsTS(self) -> Iterable[ImportSpecTS]: ...

    @abc.abstractmethod
    def getImportsPHP(self) -> Iterable[ImportSpecPHP]: ...


class DefinesCustomTypes(abc.ABC):
    @abc.abstractmethod
    def getTypesPy(self) -> "Iterable[Tuple[str, CrossType]]": ...

    @abc.abstractmethod
    def getTypesTS(self) -> "Iterable[Tuple[str, CrossType, bool]]": ...
