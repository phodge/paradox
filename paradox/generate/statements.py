import abc
import builtins
import itertools
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Tuple, Union

from paradox.expressions import (PanExpr, PanIndexAccess, PanKeyAccess,
                                 PanLiteral, Pannable, PanOmit, PanProp,
                                 PanVar, PHPPrecedence, pan, pannotomit,
                                 pyexpr)
from paradox.generate.files import FileWriter
from paradox.typing import (CrossAny, CrossDict, CrossStr, CrossType,
                            FlexiType, maybe, omittable, unflex)

try:
    # typing_extensions is only installed on python < 3.8
    # Note that typing_extensions will import Literal from typing module if possible, so if
    # typing.Literal exists, it will be used
    from typing_extensions import Literal
except ImportError:
    # on python 3.8 and newer, when typing_extensions isn't available, we can just import
    # typing.Literal directly.
    from typing import Literal  # type: ignore


ImportSpecPy = Tuple[str, Optional[List[str]]]
ImportSpecTS = Tuple[str, Optional[List[str]]]
ImportSpecPHP = Tuple[str, Optional[str]]


class NoDefault:
    pass


NO_DEFAULT = NoDefault()


def _pan_nodef(val: Union[Pannable, NoDefault]) -> Optional[PanExpr]:
    if val is NO_DEFAULT:
        return None

    # NO_DEFAULT should be the only possible instance of NoDefault. This assertion is really just
    # to satisfy mypy
    assert not isinstance(val, NoDefault)
    return pan(val)


class Statement(abc.ABC):
    def __init__(self) -> None:
        super().__init__()
        self._newtypes: List[Tuple[str, CrossType, bool]] = []

    @abc.abstractmethod
    def getImportsPy(self) -> Iterable[ImportSpecPy]: ...

    @abc.abstractmethod
    def getImportsTS(self) -> Iterable[ImportSpecTS]: ...

    @abc.abstractmethod
    def getImportsPHP(self) -> Iterable[ImportSpecPHP]: ...

    def getTypesPy(self) -> Iterable[Tuple[str, CrossType]]:
        """Yield tuples of <type name> <base type name>

        ... where <base type name> would be something a str like 'int' or 'bool'.
        """
        for name, crossbase, export in self._newtypes:
            yield name, crossbase

    def getTypesTS(self) -> Iterable[Tuple[str, CrossType, bool]]:
        """Yield tuples of <type name> <base type name> <want export>

        ... where <base type name> would be a str like 'number' or 'boolean'.
        """
        for name, crossbase, export in self._newtypes:
            yield name, crossbase, export

    def addNewType(self, name: str, base: CrossType, *, export: bool = False) -> None:
        self._newtypes.append((name, base, export))

    @abc.abstractmethod
    def writepy(self, w: FileWriter) -> None: ...

    @abc.abstractmethod
    def writets(self, w: FileWriter) -> None: ...

    @abc.abstractmethod
    def writephp(self, w: FileWriter) -> None: ...


class Statements(Statement):
    _statements: List[Statement]
    _importspy: List[ImportSpecPy]
    _importsts: List[ImportSpecTS]
    _importsphp: List[ImportSpecPHP]

    def __init__(self) -> None:
        super().__init__()
        self._statements = []
        self._importspy = []
        self._importsts = []
        self._importsphp = []

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from self._importspy
        for stmt in self._statements:
            yield from stmt.getImportsPy()

    def getImportsTS(self) -> Iterable[ImportSpecPy]:
        yield from self._importsts
        for stmt in self._statements:
            yield from stmt.getImportsTS()

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        yield from self._importsphp
        for stmt in self._statements:
            yield from stmt.getImportsPHP()

    def blank(self) -> None:
        self._statements.append(BlankLine())

    def also(self, stmt: Union[Statement, PanExpr]) -> None:
        if isinstance(stmt, PanExpr):
            self._statements.append(PanExprStatement(stmt))
        else:
            self._statements.append(stmt)

    def alsoImportPy(self, module: str, names: List[str] = None) -> None:
        self._importspy.append((module, names))

    def alsoImportTS(self, module: str, names: List[str] = None) -> None:
        self._importsts.append((module, names))

    def remark(self, text: str) -> None:
        self._statements.append(Comment(text))

    # deprecated in favour of self.also(...)
    def addStatement(self, stmt: Statement) -> None:
        self._statements.append(stmt)

    # shortcut to appending a ReturnStatement
    def alsoReturn(self, expr: Pannable) -> None:
        self._statements.append(ReturnStatement(pan(expr)))

    # shortcut to adding a statement that does list.append()
    def alsoAppend(self, list_: Pannable, value: Pannable) -> None:
        self._statements.append(ListAppendStatement(pan(list_), pan(value)))

    def alsoRaise(
        self,
        ctor: str = None,
        *,
        msg: str = None,
        expr: PanExpr = None,
    ) -> None:
        if msg is not None:
            assert expr is None
            self._statements.append(SimpleRaise(ctor, msg=msg))
        else:
            assert isinstance(expr, PanExpr)
            self._statements.append(SimpleRaise(ctor, expr=expr))

    def alsoAssign(
        self,
        var: Union[PanVar, PanIndexAccess, PanKeyAccess],
        expr: Pannable,
    ) -> None:
        self._statements.append(AssignmentStatement(var, pan(expr)))

    def alsoDeclare(
        self,
        target: Union[str, PanVar],
        type: Union[None, FlexiType, Literal["no_type"]],
        value: "Union[Pannable, builtins.ellipsis]" = ...,
    ) -> PanVar:
        declaretype = True
        if isinstance(target, PanVar):
            realtarget = target
        elif type is None:
            if not isinstance(value, PanExpr):
                raise Exception(
                    "alsoDeclare() requires a type, or target to be a PanVar"
                    ", or value to be a PanExpr with a known type"
                )
            realtarget = PanVar(target, value.getPanType())
        elif type == "no_type":
            realtarget = PanVar(target, None)
            declaretype = False
        else:
            # FIXME: get rid of type: ignore here
            realtarget = PanVar(target, unflex(type))
        self._statements.append(AssignmentStatement(
            realtarget,
            None if value is ... else pan(value),
            declare=True,
            declaretype=declaretype,
        ))
        return realtarget

    @contextmanager
    def withTryBlock(self) -> 'Iterator[TryCatchBlock]':
        block = TryCatchBlock()
        self._statements.append(block)
        yield block

    @contextmanager
    def withRawTS(self) -> 'Iterator[RawTypescript]':
        rawts = RawTypescript()
        self._statements.append(rawts)
        yield rawts

    @contextmanager
    def withCond(self, expr: PanExpr) -> 'Iterator[ConditionalBlock]':
        cond = ConditionalBlock(expr, [])
        self._statements.append(cond)
        yield cond

    @contextmanager
    def withFor(
        self,
        assign: PanVar,
        expr: Pannable,
    ) -> 'Iterator[ForLoopBlock]':
        loop = ForLoopBlock(assign, pan(expr))
        self._statements.append(loop)
        yield loop

    def writepy(self, w: FileWriter) -> None:
        for stmt in self._statements:
            stmt.writepy(w)

    def writets(self, w: FileWriter) -> None:
        for stmt in self._statements:
            stmt.writets(w)

    def writephp(self, w: FileWriter) -> None:
        for stmt in self._statements:
            stmt.writephp(w)


class StatementWithNoImports(Statement):
    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        z: List[ImportSpecPy] = []
        return z

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        return []

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        return []


class Comment(StatementWithNoImports):
    def __init__(self, text: str) -> None:
        super().__init__()

        self._text = text

    def writepy(self, w: FileWriter) -> None:
        w.line0('# ' + self._text)

    def writets(self, w: FileWriter) -> None:
        w.line0('// ' + self._text)

    def writephp(self, w: FileWriter) -> None:
        w.line0('// ' + self._text)


class BlankLine(StatementWithNoImports):
    def writepy(self, w: FileWriter) -> None:
        w.blank()

    def writets(self, w: FileWriter) -> None:
        w.blank()

    def writephp(self, w: FileWriter) -> None:
        w.blank()


class PanExprStatement(StatementWithNoImports):
    def __init__(self, expr: PanExpr) -> None:
        super().__init__()

        self._expr = expr

    def writets(self, w: FileWriter) -> None:
        w.line0(self._expr.getTSExpr()[0] + ";")

    def writepy(self, w: FileWriter) -> None:
        w.line0(self._expr.getPyExpr()[0])

    def writephp(self, w: FileWriter) -> None:
        w.line0(self._expr.getPHPExpr()[0] + ';')


class HardCodedStatement(StatementWithNoImports):
    """Used for simple statements that only need to work in Python."""
    def __init__(
        self,
        python: str = None,
        typescript: str = None,
        php: str = None,
    ) -> None:
        self._python = python
        self._typescript = typescript
        self._php = php

    def writets(self, w: FileWriter) -> None:
        if self._typescript is None:
            raise Exception("Not implemented in TS")
        w.line0(self._typescript)

    def writepy(self, w: FileWriter) -> None:
        if self._python is None:
            raise Exception("Not implemented in Python")
        w.line0(self._python)

    def writephp(self, w: FileWriter) -> None:
        if self._php is None:
            raise Exception("Not implemented in PHP")
        w.line0(self._php)


class RawTypescript(StatementWithNoImports):
    """Used for simple statements that only need to work in Python."""
    def __init__(self) -> None:
        super().__init__()

        self._lines: List[str] = []

    def rawline(self, stmt: str) -> None:
        assert "\n" not in stmt
        self._lines.append(stmt)

    def writets(self, w: FileWriter) -> None:
        for stmt in self._lines:
            w.line0(stmt)

    def writepy(self, w: FileWriter) -> None:
        raise Exception("Not implemented in Python")

    def writephp(self, w: FileWriter) -> None:
        raise Exception("Not implemented in PHP")


class SimpleRaise(StatementWithNoImports):
    _ctor: Optional[str]

    def __init__(self, ctor: str = None, *, msg: str = None, expr: PanExpr = None) -> None:
        super().__init__()

        assert msg is not None or expr is not None

        self._ctor = ctor
        self._msg = msg
        self._expr = expr

    def writepy(self, w: FileWriter) -> None:
        ctor = 'Exception'
        if self._ctor is not None:
            ctor = self._ctor
        if self._msg is None:
            assert self._expr is not None
            line = f"raise {ctor}({self._expr.getPyExpr()[0]})"
        else:
            line = f"raise {ctor}({self._msg!r})"
        w.line0(line)

    def writets(self, w: FileWriter) -> None:
        assert self._ctor is None, "Custom Exception constructor not allowed for TS"
        if self._msg is None:
            assert self._expr is not None
            line = f"throw new Error({self._expr.getPyExpr()[0]})"
        else:
            line = f"throw new Error({self._msg!r})"
        w.line0(line)

    def writephp(self, w: FileWriter) -> None:
        ctor = self._ctor or '\\Exception'
        if self._msg is None:
            assert self._expr is not None
            line = f"throw new {ctor}({self._expr.getPHPExpr()[0]});"
        else:
            # TODO: don't import this here
            from paradox.expressions import _phpstr
            line = f"throw new {ctor}({_phpstr(self._msg)});"
        w.line0(line)


class ConditionalBlock(Statements):
    _expr: PanExpr
    _statements: List[Statement]

    def __init__(self, expr: PanExpr, statements: List[Statement] = None) -> None:
        super().__init__()

        self._expr = expr
        self._statements = statements or []

    def writepy(self, w: FileWriter) -> None:
        w.line0(f'if {self._expr.getPyExpr()[0]}:')
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())
        # always put a blank line after a conditional
        w.blank()

    def writets(self, w: FileWriter) -> None:
        w.line0(f'if ({self._expr.getTSExpr()[0]}) {{')
        for stmt in self._statements:
            stmt.writets(w.with_more_indent())
        w.line0('}')

        # always put a blank line after a conditional
        w.blank()

    def writephp(self, w: FileWriter) -> None:
        w.line0(f'if ({self._expr.getPHPExpr()[0]}) {{')
        for stmt in self._statements:
            stmt.writephp(w.with_more_indent())
        w.line0('}')

        # always put a blank line after a conditional
        w.blank()


class CatchBlock(Statements):
    def __init__(self, catchexpr: str = None, catchvar: str = '') -> None:
        super().__init__()

        self.catchexpr = catchexpr
        self.catchvar = catchvar

    def writepy(self, w: FileWriter) -> None:
        intro = 'except'
        if self.catchexpr:
            intro += ' ' + self.catchexpr
            if self.catchvar:
                intro += ' as ' + self.catchvar
        intro += ':'
        w.line0(intro)
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())

    def writets(self, w: FileWriter) -> None:
        raise Exception("TODO: CatchBlock (original) doesn't do typescript")  # noqa


# TODO: get rid of the old CatchBlock
class CatchBlock2(Statements):
    _var: Optional[PanVar]

    def __init__(
        self,
        var: PanVar = None,
        *,
        pyclass: str = None,
        tsclass: str = None,
    ) -> None:
        super().__init__()

        self._var = var
        self._pyclass = pyclass
        self._tsclass = tsclass

    def writepy(self, w: FileWriter) -> None:
        # XXX: remember that for Python you almost certainly don't want a bare "except:" as that
        # would catch process signals and such.
        if self._pyclass:
            intro = "except " + self._pyclass
        else:
            intro = "except Exception"
        if self._var:
            intro += ' as ' + self._var.getPyExpr()[0]
        intro += ":"
        w.line0(intro)
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())

    def writets(self, w: FileWriter) -> None:
        raise Exception("TODO: CatchBlock2 is not directly written")  # noqa


class TryCatchBlock(Statements):
    def __init__(self) -> None:
        super().__init__()

        self._catchblocks: List[Union[CatchBlock, CatchBlock2]] = []

    @contextmanager
    def withCatchBlock(self, catchexpr: str, catchvar: str = '') -> Iterator[CatchBlock]:
        block = CatchBlock(catchexpr, catchvar)
        self._catchblocks.append(block)
        yield block

    @contextmanager
    def withCatchBlock2(
        self,
        var: PanVar,
        pyclass: str = None,
        tsclass: str = None,
    ) -> Iterator[CatchBlock2]:
        block = CatchBlock2(var, pyclass=pyclass, tsclass=tsclass)
        self._catchblocks.append(block)
        yield block

    def writepy(self, w: FileWriter) -> None:
        w.line0('try:')
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())

        # catch blocks
        for cb in self._catchblocks:
            # write out catch blocks without increasing indent
            cb.writepy(w)

    def writets(self, w: FileWriter) -> None:
        w.line0(f"try {{")
        for stmt in self._statements:
            stmt.writets(w.with_more_indent())

        assert len(self._catchblocks), "TryCatchBlock must have at least one Catch block"

        # all catch blocks must be a CatchBlock2 and have the same var name
        catchvar = None
        catchspecific: List[CatchBlock2] = []
        catchall: Optional[CatchBlock2] = None
        for cb in self._catchblocks:
            assert isinstance(cb, CatchBlock2)
            assert cb._var is not None

            # TODO: get rid of this dirty hack
            if catchvar is None:
                catchvar = cb._var._name
            else:
                assert cb._var._name == catchvar

            if cb._tsclass:
                catchspecific.append(cb)
            else:
                catchall = cb
        assert catchvar is not None

        w.line0(f"}} catch ({catchvar}) {{")
        if catchspecific:
            for cb in catchspecific:
                assert isinstance(cb, CatchBlock2)
                w.line1(f"if ({catchvar} instanceof {cb._tsclass}) {{")
                for stmt in cb._statements:
                    stmt.writets(w.with_more_indent().with_more_indent())
            if catchall:
                w.line1(f"}} else {{")
                for stmt in catchall._statements:
                    stmt.writets(w.with_more_indent().with_more_indent())
            # close off the last catch block
            w.line1(f"}}")

            if not catchall:
                # if there was no catch block added to handle any exception types, we need to
                # rethrow the exception
                w.line1(f"throw {catchvar};")
        else:
            assert catchall is not None
            for stmt in catchall._statements:
                stmt.writets(w.with_more_indent())

        w.line0(f"}}")


class ForLoopBlock(Statements):
    def __init__(
        self,
        assign: PanVar,
        expr: PanExpr,
        statements: List[Statement] = None,
    ) -> None:
        super().__init__()

        self._assign = assign
        self._expr = expr
        self._statements: List[Statement] = statements or []

    def writepy(self, w: FileWriter) -> None:
        w.line0(f'for {self._assign.getPyExpr()[0]} in {self._expr.getPyExpr()[0]}:')
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())
        # always put a blank line after a for loop
        w.blank()

    def writets(self, w: FileWriter) -> None:
        w.line0(f'for (let {self._assign.getTSExpr()[0]} of {self._expr.getTSExpr()[0]}) {{')
        for stmt in self._statements:
            stmt.writets(w.with_more_indent())
        w.line0(f'}}')
        # always put a blank line after a for loop
        w.blank()


class ReturnStatement(StatementWithNoImports):
    _expr: PanExpr

    def __init__(self, expr: PanExpr) -> None:
        super().__init__()

        self._expr = expr

    def writepy(self, w: FileWriter) -> None:
        if isinstance(self._expr, PanOmit):
            w.line0('return')
        else:
            w.line0('return ' + self._expr.getPyExpr()[0])

    def writets(self, w: FileWriter) -> None:
        if isinstance(self._expr, PanOmit):
            w.line0('return;')
        else:
            w.line0('return ' + self._expr.getTSExpr()[0] + ';')

    def writephp(self, w: FileWriter) -> None:
        if isinstance(self._expr, PanOmit):
            w.line0('return;')
        else:
            w.line0('return ' + self._expr.getPHPExpr()[0] + ';')


class ListAppendStatement(StatementWithNoImports):
    def __init__(self, list_: PanExpr, value: PanExpr) -> None:
        super().__init__()

        self._list: PanExpr = list_
        self._value: PanExpr = value

    def writepy(self, w: FileWriter) -> None:
        raise Exception("TODO: finish python code")  # noqa

    def writets(self, w: FileWriter) -> None:
        raise Exception("TODO: finish TS code")  # noqa

    def writephp(self, w: FileWriter) -> None:
        list_, prec = self._list.getPHPExpr()
        if prec.value >= PHPPrecedence.Arrow.value:
            list_ = '(' + list_ + ')'
        w.line0(list_ + '[] = ' + self._value.getPHPExpr()[0] + ';')


class AssignmentStatement(StatementWithNoImports):
    def __init__(
        self,
        target: Union[PanVar, PanKeyAccess, PanIndexAccess],
        expr: Optional[PanExpr],
        *,
        declare: bool = False,
        declaretype: bool = True,
    ) -> None:
        if expr is None:
            assert declare
        if declare:
            assert isinstance(target, PanVar), "Only a PanVar can be declared"
        self._target = target
        self._expr: Optional[PanExpr] = expr
        self._declare: bool = declare
        self._declaretype: bool = declaretype

    def writepy(self, w: FileWriter) -> None:
        left = self._target.getPyExpr()[0]
        if self._declare and self._declaretype:
            left += ': ' + self._target.getPanType().getQuotedPyType()
        if self._expr is None:
            w.line0(left)
        else:
            w.line0(f'{left} = {self._expr.getPyExpr()[0]}')

    def writets(self, w: FileWriter) -> None:
        left = self._target.getTSExpr()[0]
        if self._declare:
            left = f"let {left}"
            if self._declaretype:
                left += ": " + self._target.getPanType().getTSType()[0]

        if self._expr is None:
            w.line0(f'{left};')
        else:
            w.line0(f'{left} = {self._expr.getTSExpr()[0]};')

    def writephp(self, w: FileWriter) -> None:
        phptypes = self._target.getPanType().getPHPTypes()
        if self._declare and self._declaretype:
            w.line0(f"/** @var {phptypes[1]} */")

        left = self._target.getPHPExpr()[0]

        # you can't just make a variable declaration in PHP
        assert self._expr is not None
        w.line0(f'{left} = {self._expr.getPHPExpr()[0]};')


class DictBuilderStatement(Statement):
    _var: PanVar
    _type: CrossType

    @classmethod
    def fromPanVar(cls, var: PanVar) -> "DictBuilderStatement":
        vartype = var.getPanType()
        assert isinstance(vartype, CrossDict)
        return cls(var, vartype.getKeyType(), vartype.getValueType())

    def __init__(self, var: Union[str, PanVar], keytype: FlexiType, valtype: FlexiType) -> None:
        super().__init__()

        keytype = unflex(keytype)
        assert isinstance(keytype, CrossStr), "Only str keys are currently supported"
        realtype = CrossDict(keytype, unflex(valtype))

        if isinstance(var, str):
            self._var = PanVar(var, realtype)
        else:
            self._var = var
        self._type = realtype

        self._keys: List[Tuple[str, bool]] = []

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield 'typing', None

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        return []

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        return []

    def addPair(self, key: str, allowomit: bool) -> None:
        self._keys.append((key, allowomit))

    def writepy(self, w: FileWriter) -> None:
        inner = ', '.join([
            f'{k!r}: {k}'
            for k, allowomit in self._keys
            if not allowomit
        ])

        varstr = self._var.getPyExpr()[0]

        w.line0(f'{varstr}: {self._type.getQuotedPyType()} = {{{inner}}}')

        # now do the omittable args
        for k, allowomit in self._keys:
            if allowomit:
                # FIXME: this isn't how we want to do omitted args - we should be doing ellipsis
                expr = pannotomit(PanVar(k, None))
                w.line0(f'if {expr.getPyExpr()[0]}:')
                w.line1(f'{varstr}[{k!r}] = {k}')

    def writets(self, w: FileWriter) -> None:
        inner = ', '.join([
            f'{k!r}: {k}'
            for k, allowomit in self._keys
            if not allowomit
        ])

        varstr = self._var.getTSExpr()[0]

        w.line0(f'let {varstr}: {self._type.getTSType()[0]} = {{{inner}}};')

        # now do the omittable args
        for k, allowomit in self._keys:
            if allowomit:
                w.line0(f'if (typeof {k} !== "undefined") {{')
                w.line1(f'{varstr}[{k!r}] = {k};')
                w.line0(f'}}')

    def writephp(self, w: FileWriter) -> None:
        # TODO: don't import this here
        from paradox.expressions import _phpstr

        phptype = self._type.getPHPTypes()[0]
        if phptype:
            w.line0(f'/** @var {phptype} */')

        inner = ', '.join([
            _phpstr(k) + ' => $' + k
            for k, allowomit in self._keys
            if not allowomit
        ])

        varstr = self._var.getPHPExpr()[0]

        w.line0(f'{varstr} = [{inner}];')

        # now do the omittable args
        for k, allowomit in self._keys:
            raise Exception("omittable args aren't supported by PHP")


class FunctionSpec(Statements):
    _rettype: Optional[CrossType]

    @classmethod
    def getconstructor(cls) -> "FunctionSpec":
        return cls(
            "__init__",
            "is_constructor",
            isconstructor=True,
            ismethod=True,
        )

    def __init__(
        self,
        name: str,
        returntype: Union[FlexiType, Literal["no_return", "is_constructor"]],
        *,
        isabstract: bool = False,
        isconstructor: bool = False,
        ismethod: bool = False,
        isstaticmethod: bool = False,
        isasync: bool = False,
        docstring: List[str] = None,
    ) -> None:
        super().__init__()

        self._name = name

        if isconstructor:
            assert returntype == "is_constructor"
            self._rettype = None
        elif returntype == "is_constructor":
            raise Exception("Using returntype 'is_constructor' when isconstructor is False")
        elif returntype == "no_return":
            # function declaration should have typescript "void" or python "None"
            self._rettype = None
        else:
            # using type: ignore because we know here that returntype must be a FlexiType by this
            # point
            self._rettype = unflex(returntype)

        # list((name, type, default)))
        self._pargs: List[Tuple[str, CrossType, Optional[PanExpr]]] = []
        self._kwargs: List[Tuple[str, CrossType, Optional[PanExpr]]] = []
        self._overloads: List[FunctionSpec] = []
        self._decorators_py: List[str] = []
        self._decorators_ts: List[str] = []
        self._isabstract: bool = isabstract
        self._isconstructor: bool = isconstructor
        self._ismethod: bool = ismethod
        self._isstaticmethod: bool = isstaticmethod
        self._isasync: bool = isasync
        # TODO: add support for this in PHP/Typescript also
        self._docstring: Optional[List[str]] = docstring

    def addDecoratorPy(self, decoration: str) -> None:
        self._decorators_py.append(decoration)

    def addDecoratorTS(self, decoration: str) -> None:
        self._decorators_ts.append(decoration)

    def addOverload(
        self,
        modifications: Dict[str, Optional[FlexiType]],
        returntype: Union[FlexiType, Literal["no_return"]],
    ) -> None:
        # make a new function spec with the modifications mentioned
        overload = FunctionSpec(self._name, returntype)
        overload._ismethod = self._ismethod
        overload._isasync = self._isasync
        overload._decorators_py.append('@typing.overload')
        overload._statements.append(PanExprStatement(pyexpr('...')))

        arglist = [
            (self._pargs, overload._pargs),
            (self._kwargs, overload._kwargs),
        ]

        for source, dest in arglist:
            for name, crosstype, default in source:
                try:
                    modified: Optional[FlexiType] = modifications[name]
                except KeyError:
                    # append the argument without modifications and without a default
                    dest.append((name, crosstype, None))
                else:
                    if modified is None:
                        # the argument has been disabled in this overload
                        continue

                    # append the argument with the modified type and no default
                    dest.append((name, unflex(modified), None))

        self._overloads.append(overload)

    def addPositionalArg(
        self,
        name: str,
        crosstype: FlexiType,
        *,
        default: Union[Pannable, NoDefault] = NO_DEFAULT,
        allowomit: bool = False,
    ) -> PanVar:
        return self._addArg(
            self._pargs,
            name=name,
            crosstype=unflex(crosstype),
            default=_pan_nodef(default),
            allowomit=allowomit,
            nullable=False,
        )

    def addKWArg(
        self,
        name: str,
        sometype: FlexiType,
        *,
        default: Union[Pannable, NoDefault] = NO_DEFAULT,
        nullable: bool = False,
        allowomit: bool = False,
    ) -> PanVar:
        return self._addArg(
            self._kwargs,
            name=name,
            crosstype=unflex(sometype),
            default=_pan_nodef(default),
            allowomit=allowomit,
            nullable=nullable,
        )

    def _addArg(
        self,
        target: List[Tuple[str, CrossType, Optional[PanExpr]]],
        *,
        name: str,
        crosstype: CrossType,
        default: Optional[PanExpr],
        allowomit: bool,
        nullable: bool,
    ) -> PanVar:
        assert not len(self._overloads), 'Added an arg after an overload was defined'

        if nullable:
            crosstype = maybe(crosstype)

        if allowomit:
            crosstype = omittable(crosstype)
            if default is None:
                default = PanOmit()
        else:
            assert not isinstance(default, PanOmit)

        target.append((name, crosstype, default))
        return PanVar(name, crosstype)

    def writepy(self, w: FileWriter) -> None:
        assert not self._isasync, "async FunctionSpec not yet supported in Python"

        # first write out overloads
        for overload in self._overloads:
            overload.writepy(w)

        # blank line
        w.blank()

        # decorators
        if self._isstaticmethod:
            w.line0('@staticmethod')

        for dec in self._decorators_py:
            w.line0(dec)
        if self._isabstract:
            w.line0('@abc.abstractmethod')

        # header
        w.line0(f'def {self._name}(')

        if self._ismethod and not self._isstaticmethod:
            w.line1('self,')

        for argname, crosstype, argdefault in self._pargs:
            argstr = argname + ': ' + crosstype.getQuotedPyType()
            if argdefault is not None:
                argstr += ' = ' + argdefault.getPyExpr()[0]
            w.line1(argstr + ',')
        if len(self._kwargs):
            # mark start of kwargs
            w.line1('*,')
        for argname, argtype, argdefault in self._kwargs:
            argstr = argname
            argstr += ': ' + argtype.getQuotedPyType()
            if argdefault is not None:
                argstr += ' = ' + argdefault.getPyExpr()[0]
            w.line1(argstr + ',')

        if self._rettype is None:
            w.line0(f') -> None:')
        else:
            w.line0(f') -> {self._rettype.getQuotedPyType()}:')

        if self._docstring:
            w.line1('"""')
            for docline in self._docstring:
                w.line1(docline.strip())
            w.line1('"""')
            havebody = True

        havebody = False

        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())
            havebody = True

        if not havebody:
            w.line1('pass')

    def writets(self, w: FileWriter) -> None:
        modifiers: List[str] = []

        # TODO: do we need to write some imports?
        if self._isasync:
            assert not self._isconstructor, "async constructor not possible?"
            modifiers.append('async')

        if self._isabstract:
            modifiers.append('abstract')

        if self._isstaticmethod:
            modifiers.append('static')

        # first write out overloads
        assert not len(self._overloads), "TS overloads not supported yet"

        for decoration in self._decorators_ts:
            w.line0(decoration)

        if not len(modifiers):
            modifiers.append('public')

        name = 'constructor' if self._isconstructor else self._name
        w.line0((' '.join(modifiers)) + ' ' + name + "(")

        assert not len(self._kwargs), "TS does not support kwargs"

        # header
        for argname, crosstype, argdefault in self._pargs:
            argstr = argname + ': ' + crosstype.getTSType()[0]
            if argdefault is not None:
                argstr += ' = ' + argdefault.getTSExpr()[0]
            w.line1(argstr + ',')

        rettype: str = "void"
        if self._isconstructor:
            # no return type annotation for a class constructor
            rettype = ""
        else:
            if self._rettype is not None:
                rettype = self._rettype.getTSType()[0]
            if self._isasync:
                rettype = "Promise<" + rettype + ">"

        if self._isabstract:
            assert not len(self._statements)
            w.line0(f"): {rettype};" if rettype else ");")
        else:
            w.line0(f"): {rettype} {{" if rettype else ") {")
            for stmt in self._statements:
                stmt.writets(w.with_more_indent())
            w.line0('}')

    def writephp(self, w: FileWriter) -> None:
        modifiers: List[str] = []

        assert not self._isasync, "Async methods not possible for PHP"

        if self._isabstract:
            modifiers.append('abstract')

        if self._isstaticmethod:
            modifiers.append('static')

        # first write out overloads
        assert not len(self._overloads), "Overloads not possible in PHP"

        if self._ismethod:
            modifiers.append('public')

        name = '__construct' if self._isconstructor else self._name
        w.line0((' '.join(modifiers)) + ' function ' + name + "(")

        assert not len(self._kwargs), "PHP does not support kwargs"

        # header
        argnum = 0
        comma = ','
        for argname, crosstype, argdefault in self._pargs:
            argnum += 1
            if argnum == len(self._pargs):
                comma = ''
            argstr = '$' + argname
            phptype = crosstype.getPHPTypes()[0]
            if phptype:
                argstr = phptype + ' ' + argstr
            if argdefault is not None:
                argstr += ' = ' + argdefault.getPHPExpr()[0]
            w.line1(argstr + comma)

        rettype: str = ""
        if not self._isconstructor and self._rettype is not None:
            rettype = self._rettype.getPHPTypes()[0] or ""

        if rettype:
            rettype = ": " + rettype

        if self._isabstract:
            assert not len(self._statements)
            w.line0(f"){rettype};")
        else:
            w.line0(f"){rettype} {{")
            for stmt in self._statements:
                stmt.writephp(w.with_more_indent())
            w.line0('}')

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from super().getImportsPy()

        if self._isabstract:
            yield 'abc', None
        for stmt in self._statements:
            yield from stmt.getImportsPy()

        crosstypes: List[CrossType] = [a[1] for a in itertools.chain(self._pargs, self._kwargs)]

        if self._rettype is not None:
            crosstypes.append(self._rettype)

        for crosstype in crosstypes:
            for module, name in crosstype.getPyImports():
                if name:
                    yield module, [name]
                else:
                    yield module, None

        for overload in self._overloads:
            yield from overload.getImportsPy()

        # XXX: also need types out of the arg types / return types

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        yield from super().getImportsTS()

        for stmt in self._statements:
            yield from stmt.getImportsTS()

        for overload in self._overloads:
            yield from overload.getImportsTS()

        # XXX: also need types out of the arg types / return types


@dataclass
class ClassProperty:
    propname: str
    proptype: CrossType
    propdefault: Optional[PanExpr]
    tsobservable: bool = False
    tsreadonly: bool = False


class ClassSpec(Statement):
    _importspy: List[ImportSpecPy]
    _importsts: List[ImportSpecTS]
    _importsphp: List[ImportSpecPHP]

    def __init__(
        self,
        name: str,
        *,
        # TODO: `bases` is just for python now, so we should rename it
        bases: List[str] = None,
        docstring: List[str] = None,
        isabstract: bool = False,
        isdataclass: bool = False,
        tsexport: bool = False,
        tsbase: str = None,
        appendto: Statements = None,
    ) -> None:
        super().__init__()

        self._name = name
        self._bases = bases or []
        self._docstring = docstring
        self._isabstract = isabstract
        self._isdataclass = isdataclass

        self._methods: List[FunctionSpec] = []
        self._remarks: List[str] = []
        self._properties: List[ClassProperty] = []
        self._initargs: List[Tuple[str, CrossType, Optional[PanExpr]]] = []
        self._initdefaults: List[Tuple[str, PanExpr]] = []
        self._decorators: List[str] = []
        self._tsexport: bool = tsexport
        self._tsbase: Optional[str] = tsbase

        self._importspy = []
        self._importsts = []
        self._importsphp = []

        if appendto:
            appendto.also(self)

    @property
    def classname(self) -> str:
        return self._name

    def createMethod(
        self,
        name: str,
        returntype: Union[FlexiType, Literal["no_return"]],
        *,
        isabstract: bool = False,
        isstaticmethod: bool = False,
        isasync: bool = False,
        docstring: List[str] = None,
    ) -> FunctionSpec:
        spec = FunctionSpec(
            name,
            returntype,
            isabstract=isabstract,
            ismethod=True,
            isstaticmethod=isstaticmethod,
            isasync=isasync,
            docstring=docstring,
        )
        self._methods.append(spec)
        return spec

    def addProperty(
        self,
        name: str,
        type: FlexiType,
        *,
        initarg: bool = False,
        default: Union[Pannable, NoDefault] = NO_DEFAULT,
        tsobservable: bool = False,
        tsreadonly: bool = False,
    ) -> PanProp:
        crosstype = unflex(type)
        realdefault = _pan_nodef(default)
        if initarg:
            self._initargs.append((name, crosstype, realdefault))
        elif realdefault is not None:
            self._initdefaults.append((name, realdefault))

        self._properties.append(ClassProperty(
            propname=name,
            proptype=crosstype,
            propdefault=realdefault,
            tsobservable=tsobservable,
            tsreadonly=tsreadonly,
        ))
        return PanProp(name, crosstype, None)

    def _getInitSpec(self, lang: Literal["python", "typescript", "php"]) -> Optional[FunctionSpec]:
        initdefaults = self._initdefaults

        if lang in ("typescript", "php"):
            # if the language is typescript or PHP, we don't need to assign PanLiteral default
            # values because these were already done in the class body
            initdefaults = [d for d in initdefaults if not isinstance(d[1], PanLiteral)]

        # do we actually need the __init__() method or was it a noop?
        if not (self._initargs or initdefaults):
            return None

        initspec = FunctionSpec.getconstructor()
        for name, crosstype, pandefault in self._initargs:
            initspec.addPositionalArg(
                name,
                crosstype,
                default=NO_DEFAULT if pandefault is None else pandefault,
            )
            initspec.alsoAssign(PanProp(name, CrossAny(), None), PanVar(name, None))

        if self._bases and lang == "python":
            initspec.addPositionalArg('*args', CrossAny())
            initspec.addPositionalArg('**kwargs', CrossAny())

        # also call super's init
        if self._bases:
            initspec.also(HardCodedStatement(
                python='super().__init__(*args, **kwargs)',
                typescript='super();',
                php='parent::__construct();',
            ))
        elif self._tsbase and lang == "typescript":
            initspec.also(HardCodedStatement(
                typescript='super();',
            ))

        # do we need positional args for any of the properties?
        for name, default in initdefaults:
            initspec.alsoAssign(PanProp(name, CrossAny(), None), default)

        return initspec

    def alsoImportPy(self, module: str, names: List[str] = None) -> None:
        self._importspy.append((module, names))

    def alsoImportTS(self, module: str, names: List[str] = None) -> None:
        self._importsts.append((module, names))

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from self._importspy
        if self._isabstract:
            yield 'abc', None
        if self._isdataclass:
            yield 'dataclasses', None
        constructor = self._getInitSpec("python")
        if constructor:
            yield from constructor.getImportsPy()
        for method in self._methods:
            yield from method.getImportsPy()

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        yield from self._importsts

        for prop in self._properties:
            if prop.tsobservable:
                yield 'mobx', ['observable']
                break
        constructor = self._getInitSpec("typescript")
        if constructor:
            yield from constructor.getImportsTS()
        for method in self._methods:
            yield from method.getImportsTS()

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        yield from self._importsphp

        constructor = self._getInitSpec("php")
        if constructor:
            yield from constructor.getImportsPHP()
        for method in self._methods:
            yield from method.getImportsPHP()

    def remark(self, comment: str) -> None:
        self._remarks.append(comment)

    def writepy(self, w: FileWriter) -> None:
        havebody = False
        bases = self._bases[:]

        # write out class header
        if self._isabstract:
            bases.append('abc.ABC')
        if self._isdataclass:
            w.line0('@dataclasses.dataclass')

        parents = ', '.join(bases)
        if parents:
            parents = '(' + parents + ')'
        w.line0(f'class {self._name}{parents}:')
        if self._docstring:
            w.line1('"""')
            for docline in self._docstring:
                w.line1(docline.strip())
            w.line1('"""')
            w.blank()
            havebody = True

        # first write out properties
        for prop in self._properties:
            w.line1(f'{prop.propname}: {prop.proptype.getQuotedPyType()}')
        if self._properties:
            w.blank()
            havebody = True

        # add an __init__() method to set default values
        initspec = self._getInitSpec("python")
        if initspec:
            initspec.writepy(w.with_more_indent())
            w.blank()
            havebody = True

        # all other methods
        for method in self._methods:
            method.writepy(w.with_more_indent())
            w.blank()
            havebody = True

        for comment in self._remarks:
            w.line1('# ' + comment)
            w.blank()

        if not havebody:
            w.line1('pass')

    def writets(self, w: FileWriter) -> None:
        prefix = ''
        if self._tsexport:
            prefix = 'export '

        if self._isabstract:
            prefix += 'abstract '

        extends = ''
        if self._tsbase:
            extends = f" extends {self._tsbase}"

        w.line0(f"{prefix}class {self._name}{extends} {{")

        needemptyline = False

        if self._docstring:
            for docline in self._docstring:
                w.line1('// ' + docline.strip())
            needemptyline = True

        # first write out properties
        if self._properties and needemptyline:
            w.blank()
        for prop in self._properties:
            if prop.tsobservable:
                w.blank()
                w.line1(f'@observable')
            if prop.tsreadonly:
                prefix = 'readonly '
            else:
                prefix = 'public '
            assign = ''

            # only assign values in the class body if the value is a literal
            if prop.propdefault and isinstance(prop.propdefault, PanLiteral):
                assign = ' = ' + prop.propdefault.getTSExpr()[0]

            w.line1(f'{prefix}{prop.propname}: {prop.proptype.getTSType()[0]}{assign};')
            needemptyline = True

        # add an __init__() method to set default values
        constructor = self._getInitSpec("typescript")
        if constructor:
            if needemptyline:
                w.blank()
            constructor.writets(w.with_more_indent())
            needemptyline = True

        # all other methods
        for method in self._methods:
            if needemptyline:
                w.blank()
            method.writets(w.with_more_indent())
            needemptyline = True

        for comment in self._remarks:
            w.line1('// ' + comment)
            w.blank()

        w.line0("}")

    def writephp(self, w: FileWriter) -> None:
        prefix = ''

        if self._isabstract:
            prefix += 'abstract '

        if self._docstring:
            w.line0('/**')
            for docline in self._docstring:
                w.line0(' * ' + docline.strip())
            w.line0(' */')

        extends = ''
        if len(self._bases):
            assert len(self._bases) <= 1
            extends = ' extends ' + self._bases[0]

        w.line0(f"{prefix}class {self._name}{extends} {{")

        needemptyline = False

        # first write out properties
        for prop in self._properties:
            assign = ''

            # only assign values in the class body if the value is a literal
            if prop.propdefault and isinstance(prop.propdefault, PanLiteral):
                assign = ' = ' + prop.propdefault.getPHPExpr()[0]

            phptypes = prop.proptype.getPHPTypes()
            w.line1(f'/** @var {phptypes[1]} */')
            w.line1(f'public ${prop.propname}{assign};')
            needemptyline = True

        # add an __init__() method to set default values
        constructor = self._getInitSpec("php")
        if constructor:
            if needemptyline:
                w.blank()
            constructor.writephp(w.with_more_indent())
            needemptyline = True

        # all other methods
        for method in self._methods:
            if needemptyline:
                w.blank()
            method.writephp(w.with_more_indent())
            needemptyline = True

        if needemptyline:
            for comment in self._remarks:
                w.line1('// ' + comment)
                w.blank()

        w.line0("}")


class InterfaceSpec(Statement):
    def __init__(
        self,
        name: str,
        *,
        tsexport: bool = False,
        appendto: Statements = None
    ) -> None:
        super().__init__()

        self._name = name
        self._properties: List[Tuple[str, CrossType]] = []
        self._tsexport: bool = tsexport

        if appendto:
            appendto.also(self)

    def addProperty(
        self,
        name: str,
        type: FlexiType,
    ) -> None:
        self._properties.append((name, unflex(type)))

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from super().getImportsPy()
        for name, crosstype in self._properties:
            raise Exception("TODO: get imports from property types")  # noqa
            yield from crosstype.getImportsPy()

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        raise NotImplementedError("TODO: not implemented")

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        for name, crosstype in self._properties:
            # TODO: get imports from crosstype
            # yield from crosstype.getImportsTS()
            pass
        return []

    def writepy(self, w: FileWriter) -> None:
        raise NotImplementedError("InterfaceSpec can't generate python code")  # noqa

    def writets(self, w: FileWriter) -> None:
        export = 'export ' if self._tsexport else ''
        w.line0(f"{export}interface {self._name} {{")
        for propname, proptype in self._properties:
            w.line1(f"{propname}: {proptype.getTSType()[0]};")
        w.line0(f"}}")

    def writephp(self, w: FileWriter) -> None:
        raise NotImplementedError("TODO: not implemented")
