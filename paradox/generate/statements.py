import abc
import builtins
import itertools
from contextlib import contextmanager
from dataclasses import dataclass
from typing import (
    Dict,
    Iterable,
    Iterator,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

from paradox.expressions import (
    PanExpr,
    PanIndexAccess,
    PanKeyAccess,
    PanLiteral,
    Pannable,
    PanOmit,
    PanProp,
    PanVar,
    PHPPrecedence,
    PyPrecedence,
    TSPrecedence,
    pan,
    pannotomit,
    pyexpr,
)
from paradox.interfaces import (
    AcceptsStatements,
    AlsoParam,
    ImplementationMissing,
    ImportSpecPHP,
    ImportSpecPy,
    ImportSpecTS,
    InvalidLogic,
    NotSupportedError,
    TypeMissing,
    WantsImports,
)
from paradox.output import FileWriter
from paradox.typing import (
    CrossAny,
    CrossDict,
    CrossStr,
    CrossType,
    FlexiType,
    maybe,
    omittable,
    unflex,
)


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


class Statement(WantsImports, abc.ABC):
    @abc.abstractmethod
    def writepy(self, w: FileWriter) -> int: ...

    @abc.abstractmethod
    def writets(self, w: FileWriter) -> None: ...

    @abc.abstractmethod
    def writephp(self, w: FileWriter) -> None: ...


class _StatementWithCustomImports(Statement):
    _importspy: List[ImportSpecPy]
    _importsts: List[ImportSpecTS]
    _importsphp: List[ImportSpecPHP]

    def __init__(self) -> None:
        super().__init__()

        self._importspy = []
        self._importsts = []
        self._importsphp = []

    # TODO: add an alsoImportPHP()
    def alsoImportPy(self, module: str, names: List[str] = None) -> None:
        if names is None:
            self._importspy.append((module, None))
        else:
            for name in names:
                self._importspy.append((module, name))

    def alsoImportTS(self, module: str, names: List[str] = None) -> None:
        self._importsts.append((module, names))

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from super().getImportsPy()
        yield from self._importspy

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        yield from super().getImportsTS()
        yield from self._importsts

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        yield from super().getImportsPHP()
        yield from self._importsphp


class Statements(_StatementWithCustomImports, AcceptsStatements):
    _statements: List[Statement]

    def __init__(self) -> None:
        super().__init__()
        self._statements = []

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from super().getImportsPy()
        for stmt in self._statements:
            yield from stmt.getImportsPy()

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        yield from super().getImportsTS()
        for stmt in self._statements:
            yield from stmt.getImportsTS()

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        yield from super().getImportsPHP()
        for stmt in self._statements:
            yield from stmt.getImportsPHP()

    def blank(self) -> None:
        self._statements.append(BlankLine())

    def also(self, stmt_or_expr: AlsoParam) -> AlsoParam:
        if isinstance(stmt_or_expr, PanExpr):
            stmt: Statement = PanExprStatement(stmt_or_expr)
        else:
            stmt = cast(Statement, stmt_or_expr)
        self._statements.append(stmt)
        return cast(AlsoParam, stmt)

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

    # TODO: this should accept language-specific constructors so that clients don't need to insert
    # the a ctor that matches the target language
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
        self._statements.append(
            AssignmentStatement(
                realtarget,
                None if value is ... else pan(value),
                declare=True,
                declaretype=declaretype,
            )
        )
        return realtarget

    @contextmanager
    def withTryBlock(self) -> "Iterator[TryCatchBlock]":
        block = TryCatchBlock()
        self._statements.append(block)
        yield block

    @contextmanager
    def withRawTS(self) -> "Iterator[RawTypescript]":
        rawts = RawTypescript()
        self._statements.append(rawts)
        yield rawts

    @contextmanager
    def withCond(self, expr: PanExpr) -> "Iterator[ConditionalBlock]":
        cond = ConditionalBlock(expr, [])
        self._statements.append(cond)
        yield cond

    @contextmanager
    def withFor(
        self,
        assign: PanVar,
        expr: Pannable,
    ) -> "Iterator[ForLoopBlock]":
        loop = ForLoopBlock(assign, pan(expr))
        self._statements.append(loop)
        yield loop

    @contextmanager
    def withDictIter(
        self,
        v_dict: PanExpr,
        v_val: PanVar,
        v_key: PanVar = None,
    ) -> "Iterator[DictLoopBlock]":
        loop = DictLoopBlock(v_dict, v_val, v_key)
        self._statements.append(loop)
        yield loop

    def writepy(self, w: FileWriter) -> int:
        written = 0
        for stmt in self._statements:
            written += stmt.writepy(w)
        return written

    def writets(self, w: FileWriter) -> None:
        for stmt in self._statements:
            stmt.writets(w)

    def writephp(self, w: FileWriter) -> None:
        for stmt in self._statements:
            stmt.writephp(w)


class StatementWithNoImports(Statement):
    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        return []

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        return []

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        return []


class Comment(StatementWithNoImports):
    def __init__(self, text: str) -> None:
        super().__init__()

        self._text = text

    def writepy(self, w: FileWriter) -> int:
        w.line0("# " + self._text)
        return 0

    def writets(self, w: FileWriter) -> None:
        w.line0("// " + self._text)

    def writephp(self, w: FileWriter) -> None:
        w.line0("// " + self._text)


class BlankLine(StatementWithNoImports):
    def writepy(self, w: FileWriter) -> int:
        w.blank()
        return 0

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

    def writepy(self, w: FileWriter) -> int:
        w.line0(self._expr.getPyExpr()[0])
        return 1

    def writephp(self, w: FileWriter) -> None:
        w.line0(self._expr.getPHPExpr()[0] + ";")


class HardCodedStatement(StatementWithNoImports):
    """Used for simple statements that only need to work in Python."""

    def __init__(
        self,
        *,
        python: "Union[str, None, builtins.ellipsis]" = ...,
        typescript: "Union[str, None, builtins.ellipsis]" = ...,
        php: "Union[str, None, builtins.ellipsis]" = ...,
    ) -> None:
        self._python = python
        self._typescript = typescript
        self._php = php

    def writets(self, w: FileWriter) -> None:
        if self._typescript is ...:
            raise ImplementationMissing(
                "HardCodedStatement was not given a TypeScript implementation"
            )
        if self._typescript is not None:
            # XXX: mypy doesn't realise that self._typescript cannot be ...
            w.line0(self._typescript)  # type: ignore

    def writepy(self, w: FileWriter) -> int:
        if self._python is ...:
            raise ImplementationMissing("HardCodedStatement was not given a Python implementation")

        if self._python is None:
            return 0

        # XXX: mypy doesn't realise that self._python cannot be ...
        w.line0(self._python)  # type: ignore
        return 1

    def writephp(self, w: FileWriter) -> None:
        if self._php is ...:
            raise ImplementationMissing("HardCodedStatement was not given a PHP implementation")
        if self._php is not None:
            # XXX: mypy doesn't realise that self._php cannot be ...
            w.line0(self._php)  # type: ignore


class RawTypescript(StatementWithNoImports):
    # TODO: deprecate this in favour of HardCodedStatement

    def __init__(self) -> None:
        super().__init__()

        self._lines: List[str] = []

    def rawline(self, stmt: str) -> None:
        assert "\n" not in stmt
        self._lines.append(stmt)

    def writets(self, w: FileWriter) -> None:
        for stmt in self._lines:
            w.line0(stmt)

    def writepy(self, w: FileWriter) -> int:
        raise Exception("Not implemented in Python")

    def writephp(self, w: FileWriter) -> None:
        raise Exception("Not implemented in PHP")


# TODO: this should accept language-specific constructors so that clients don't
# need to insert the a ctor that matches the target language
class SimpleRaise(StatementWithNoImports):
    _ctor: Optional[str]

    def __init__(self, ctor: str = None, *, msg: str = None, expr: PanExpr = None) -> None:
        super().__init__()

        assert msg is not None or expr is not None

        self._ctor = ctor
        self._msg = msg
        self._expr = expr

    def writepy(self, w: FileWriter) -> int:
        ctor = "Exception"
        if self._ctor is not None:
            ctor = self._ctor
        if self._msg is None:
            assert self._expr is not None
            line = f"raise {ctor}({self._expr.getPyExpr()[0]})"
        else:
            line = f"raise {ctor}({self._msg!r})"
        w.line0(line)
        return 1

    def writets(self, w: FileWriter) -> None:
        ctor = self._ctor or "Error"
        if self._msg is None:
            assert self._expr is not None
            line = f"throw new {ctor}({self._expr.getPyExpr()[0]});"
        else:
            line = f"throw new {ctor}({self._msg!r});"
        w.line0(line)

    def writephp(self, w: FileWriter) -> None:
        ctor = self._ctor or "\\Exception"
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
    _alternates: List[Tuple[PanExpr, Statements]]
    _else: Optional[Statements]

    def __init__(self, expr: PanExpr, statements: List[Statement] = None) -> None:
        super().__init__()

        self._expr = expr
        self._statements = statements or []
        self._alternates = []
        self._else = None

    @contextmanager
    def withElseif(self, expr: PanExpr) -> "Iterator[Statements]":
        stmts = Statements()
        self._alternates.append((expr, stmts))
        yield stmts

    @contextmanager
    def withElse(self) -> "Iterator[Statements]":
        assert not self._else
        stmts = Statements()
        self._else = stmts
        yield stmts

    def writepy(self, w: FileWriter) -> int:
        w.line0(f"if {self._expr.getPyExpr()[0]}:")
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())

        # TODO: if none of self._statements wrote a line of code, we should inject a 'pass'
        for altexpr, altstmt in self._alternates:
            w.line0(f"elif {altexpr.getPyExpr()[0]}:")
            if not altstmt.writepy(w.with_more_indent()):
                w.line1("pass")

        if self._else:
            w.line0(f"else:")
            if not self._else.writepy(w.with_more_indent()):
                # TODO: test this code path
                w.line1("pass")

        # always put a blank line after a conditional
        w.blank()
        return 1

    def writets(self, w: FileWriter) -> None:
        w.line0(f"if ({self._expr.getTSExpr()[0]}) {{")
        for stmt in self._statements:
            stmt.writets(w.with_more_indent())

        for altexpr, altstmt in self._alternates:
            w.line0(f"}} else if ({altexpr.getTSExpr()[0]}) {{")
            altstmt.writets(w.with_more_indent())

        if self._else:
            w.line0(f"}} else {{")
            self._else.writets(w.with_more_indent())

        w.line0("}")

        # always put a blank line after a conditional
        w.blank()

    def writephp(self, w: FileWriter) -> None:
        w.line0(f"if ({self._expr.getPHPExpr()[0]}) {{")
        for stmt in self._statements:
            stmt.writephp(w.with_more_indent())

        for altexpr, altstmt in self._alternates:
            w.line0(f"}} elseif ({altexpr.getPHPExpr()[0]}) {{")
            altstmt.writephp(w.with_more_indent())

        if self._else:
            w.line0(f"}} else {{")
            self._else.writephp(w.with_more_indent())

        w.line0("}")

        # always put a blank line after a conditional
        w.blank()


class CatchBlock(Statements):
    def __init__(self, catchexpr: str = None, catchvar: str = "") -> None:
        super().__init__()

        self.catchexpr = catchexpr
        self.catchvar = catchvar

    def writepy(self, w: FileWriter) -> int:
        intro = "except"
        if self.catchexpr:
            intro += " " + self.catchexpr
            if self.catchvar:
                intro += " as " + self.catchvar
        intro += ":"
        w.line0(intro)
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())

        # TODO: if none of self._statements wrote a line of code, we should inject a 'pass'

        return 1

    def writets(self, w: FileWriter) -> None:
        raise Exception("TODO: CatchBlock (original) doesn't do typescript")  # noqa

    def writephp(self, w: FileWriter) -> None:
        if not self.catchexpr:
            raise Exception("CatchBlock cannot be turned to PHP without a catchexpr")

        intro = "} catch (" + self.catchexpr
        intro += " $" + (self.catchvar or "_")
        intro += ") {"
        w.line0(intro)
        for stmt in self._statements:
            stmt.writephp(w.with_more_indent())


# TODO: get rid of the old CatchBlock
class CatchBlock2(Statements):
    _var: Optional[PanVar]

    def __init__(
        self,
        var: PanVar = None,
        *,
        pyclass: str = None,
        tsclass: str = None,
        phpclass: str = None,
    ) -> None:
        super().__init__()

        self._var = var
        self._pyclass = pyclass
        self._tsclass = tsclass
        self._phpclass = phpclass

    def writepy(self, w: FileWriter) -> int:
        # XXX: remember that for Python you almost certainly don't want a bare "except:" as that
        # would catch process signals and such.
        if self._pyclass:
            intro = "except " + self._pyclass
        else:
            intro = "except Exception"
        if self._var:
            intro += " as " + self._var.getPyExpr()[0]
        intro += ":"
        w.line0(intro)
        body_count = 0
        for stmt in self._statements:
            body_count += stmt.writepy(w.with_more_indent())

        # TODO: this logic needs to be copied across to other types of Statements
        if not body_count:
            w.line1("pass")

        return 1

    def writets(self, w: FileWriter) -> None:
        raise Exception("TODO: CatchBlock2 is not directly written")  # noqa

    def writephp(self, w: FileWriter) -> None:
        intro = "} catch (" + (self._phpclass or "Exception")
        intro += " $" + (self._var.rawname if self._var else "_")
        intro += ") {"
        w.line0(intro)
        for stmt in self._statements:
            stmt.writephp(w.with_more_indent())


class FinallyBlock(Statements):
    def writepy(self, w: FileWriter) -> int:
        w.line0("finally:")
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())

        # TODO: inject 'pass' statement if there no statements wrote a body
        return 1

    def writets(self, w: FileWriter) -> None:
        w.line0("} finally {")
        for stmt in self._statements:
            stmt.writets(w.with_more_indent())

    def writephp(self, w: FileWriter) -> None:
        w.line0("} finally {")
        for stmt in self._statements:
            stmt.writephp(w.with_more_indent())


class TryCatchBlock(Statements):
    _finallyblock: Optional[FinallyBlock] = None

    def __init__(self) -> None:
        super().__init__()

        self._catchblocks: List[Union[CatchBlock, CatchBlock2]] = []

    @contextmanager
    def withCatchBlock(self, catchexpr: str, catchvar: str = "") -> Iterator[CatchBlock]:
        block = CatchBlock(catchexpr, catchvar)
        self._catchblocks.append(block)
        yield block

    @contextmanager
    def withCatchBlock2(
        self,
        var: PanVar = None,
        pyclass: str = None,
        tsclass: str = None,
        phpclass: str = None,
    ) -> Iterator[CatchBlock2]:
        block = CatchBlock2(var, pyclass=pyclass, tsclass=tsclass, phpclass=phpclass)
        self._catchblocks.append(block)
        yield block

    @contextmanager
    def withFinallyBlock(self) -> Iterator[FinallyBlock]:
        if self._finallyblock:
            raise InvalidLogic("Cannot have multiple FinallyBlocks under a single TryCatchBlock")

        block = FinallyBlock()
        self._finallyblock = block
        yield block

    def writepy(self, w: FileWriter) -> int:
        w.line0("try:")
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())

        # TODO: if none of self._statements wrote a line of code, we should inject a 'pass'

        # catch blocks
        for cb in self._catchblocks:
            # write out catch blocks without increasing indent
            cb.writepy(w)

        if self._finallyblock:
            # write out finally: block without increasing indent
            self._finallyblock.writepy(w)

        return 1

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
            if cb._var is None:
                pass
            elif catchvar is None:
                catchvar = cb._var._name
            elif cb._var._name != catchvar:
                # TODO: unit test this code path
                raise InvalidLogic(
                    "Every CatchBlock2 must have the same varname for generating TypeScript"
                )

            if cb._tsclass:
                catchspecific.append(cb)
            elif catchall is not None:
                # TODO: unit test this code path
                raise InvalidLogic(
                    "Cannot have multiple CatchBlock2 with no TypeScript exception type specified",
                )
            else:
                catchall = cb
        if catchvar is None and len(catchspecific):
            # TODO: test this code path
            raise InvalidLogic(
                "at least one CatchBlock2 must have a varname for generating typescript"
            )

        w.line0(f"}} catch ({catchvar}) {{")
        if catchspecific:
            first = True
            for cb in catchspecific:
                assert isinstance(cb, CatchBlock2)
                if first:
                    construct = "if"
                    first = False
                else:
                    construct = "} else if"
                w.line1(f"{construct} ({catchvar} instanceof {cb._tsclass}) {{")
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

        if self._finallyblock:
            # write out finally: block without increasing indent
            self._finallyblock.writets(w)

        w.line0(f"}}")

    def writephp(self, w: FileWriter) -> None:
        w.line0("try {")
        for stmt in self._statements:
            stmt.writephp(w.with_more_indent())

        # catch blocks
        for cb in self._catchblocks:
            # write out catch blocks without increasing indent
            cb.writephp(w)

        if self._finallyblock:
            # write out finally: block without increasing indent
            self._finallyblock.writephp(w)

        w.line0("}")


class DictLoopBlock(Statements):
    def __init__(
        self,
        expr: PanExpr,
        v_val: PanVar,
        v_key: PanVar = None,
        statements: List[Statement] = None,
    ) -> None:
        super().__init__()

        self._v_key = v_key
        self._v_val = v_val
        self._expr = expr
        self._statements: List[Statement] = statements or []

    def writepy(self, w: FileWriter) -> int:
        v_val = self._v_val.getPyExpr()[0]
        if self._v_key:
            v_key = self._v_key.getPyExpr()[0]
            w.line0(f"for {v_key}, {v_val} in ({self._expr.getPyExpr()[0]}).items():")
        else:
            w.line0(f"for {v_val} in ({self._expr.getPyExpr()[0]}).values():")
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())

        # TODO: if none of self._statements wrote a line of code, we should inject a 'pass'

        # always put a blank line after a for loop
        w.blank()
        return 1

    def writets(self, w: FileWriter) -> None:
        raise Exception("TODO: implement this for TS")  # noqa

    def writephp(self, w: FileWriter) -> None:
        assignto = self._v_val.getPHPExpr()[0]
        if self._v_key:
            assignto = self._v_key.getPHPExpr()[0] + " => " + assignto
        w.line0(f"foreach ({self._expr.getPHPExpr()[0]} as {assignto}) {{")
        for stmt in self._statements:
            stmt.writephp(w.with_more_indent())
        w.line0(f"}}")
        # always put a blank line after a for loop
        w.blank()


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

    def writepy(self, w: FileWriter) -> int:
        w.line0(f"for {self._assign.getPyExpr()[0]} in {self._expr.getPyExpr()[0]}:")
        for stmt in self._statements:
            stmt.writepy(w.with_more_indent())

        # TODO: if none of self._statements wrote a line of code, we should inject a 'pass'

        # always put a blank line after a for loop
        w.blank()
        return 1

    def writets(self, w: FileWriter) -> None:
        w.line0(f"for (let {self._assign.getTSExpr()[0]} of {self._expr.getTSExpr()[0]}) {{")
        for stmt in self._statements:
            stmt.writets(w.with_more_indent())
        w.line0(f"}}")
        # always put a blank line after a for loop
        w.blank()

    def writephp(self, w: FileWriter) -> None:
        w.line0(f"foreach ({self._expr.getPHPExpr()[0]} as {self._assign.getPHPExpr()[0]}) {{")
        for stmt in self._statements:
            stmt.writephp(w.with_more_indent())
        w.line0(f"}}")
        # always put a blank line after a for loop
        w.blank()


class ReturnStatement(StatementWithNoImports):
    _expr: PanExpr

    def __init__(self, expr: PanExpr) -> None:
        super().__init__()

        self._expr = expr

    def writepy(self, w: FileWriter) -> int:
        if isinstance(self._expr, PanOmit):
            w.line0("return")
        else:
            w.line0("return " + self._expr.getPyExpr()[0])
        return 1

    def writets(self, w: FileWriter) -> None:
        if isinstance(self._expr, PanOmit):
            w.line0("return;")
        else:
            w.line0("return " + self._expr.getTSExpr()[0] + ";")

    def writephp(self, w: FileWriter) -> None:
        if isinstance(self._expr, PanOmit):
            w.line0("return;")
        else:
            w.line0("return " + self._expr.getPHPExpr()[0] + ";")


class ListAppendStatement(StatementWithNoImports):
    def __init__(self, list_: PanExpr, value: PanExpr) -> None:
        super().__init__()

        self._list: PanExpr = list_
        self._value: PanExpr = value

    def writepy(self, w: FileWriter) -> int:
        list_, prec = self._list.getPyExpr()
        if prec.value >= PyPrecedence.MultDiv.value:
            list_ = "(" + list_ + ")"
        w.line0(list_ + ".append(" + self._value.getPyExpr()[0] + ")")
        return 1

    def writets(self, w: FileWriter) -> None:
        list_, prec = self._list.getTSExpr()
        if prec.value >= TSPrecedence.MultDiv.value:
            list_ = "(" + list_ + ")"
        w.line0(list_ + ".push(" + self._value.getTSExpr()[0] + ");")

    def writephp(self, w: FileWriter) -> None:
        list_, prec = self._list.getPHPExpr()
        if prec.value > PHPPrecedence.Arrow.value:
            list_ = "(" + list_ + ")"
        w.line0(list_ + "[] = " + self._value.getPHPExpr()[0] + ";")


class AssignmentStatement(Statement):
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

        if declare and declaretype:
            try:
                # make sure the target has type information
                self._target.getPanType()
            except TypeMissing:
                raise InvalidLogic(
                    f"{self.__class__.__name__} target does not have type information"
                )

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        # no imports are required for declaring a PHP type
        return []

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        return []

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from super().getImportsPy()
        if self._declare and self._declaretype:
            pantype: CrossType = self._target.getPanType()
            yield from pantype.getPyImports()

    def writepy(self, w: FileWriter) -> int:
        left = self._target.getPyExpr()[0]
        if self._declare and self._declaretype:
            left += ": " + self._target.getPanType().getQuotedPyType()
        if self._expr is None:
            w.line0(left)
        else:
            w.line0(f"{left} = {self._expr.getPyExpr()[0]}")
        return 1

    def writets(self, w: FileWriter) -> None:
        left = self._target.getTSExpr()[0]
        if self._declare:
            left = f"let {left}"
            if self._declaretype:
                left += ": " + self._target.getPanType().getTSType()[0]

        if self._expr is None:
            w.line0(f"{left};")
        else:
            w.line0(f"{left} = {self._expr.getTSExpr()[0]};")

    def writephp(self, w: FileWriter) -> None:
        if self._declare and self._declaretype:
            phptypes = self._target.getPanType().getPHPTypes()
            w.line0(f"/** @var {phptypes[1]} */")

        left = self._target.getPHPExpr()[0]

        # you can't just make a variable declaration in PHP
        assert self._expr is not None
        w.line0(f"{left} = {self._expr.getPHPExpr()[0]};")


class DictBuilderStatement(Statement):
    _var: PanVar
    _type: CrossDict

    @classmethod
    def fromPanVar(cls, var: PanVar) -> "DictBuilderStatement":
        vartype = var.getPanType()
        assert isinstance(vartype, CrossDict)
        return cls(var, vartype.getKeyType(), vartype.getValueType())

    def __init__(self, var: Union[str, PanVar], keytype: FlexiType, valtype: FlexiType) -> None:
        super().__init__()

        keytype = unflex(keytype)
        if not isinstance(keytype, CrossStr):
            raise NotSupportedError("Only str keys are currently supported")
        realtype = CrossDict(keytype, unflex(valtype))

        if isinstance(var, str):
            self._var = PanVar(var, realtype)
        else:
            self._var = var
        self._type = realtype

        self._keys: List[Tuple[str, bool]] = []

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from super().getImportsPy()
        yield from self._type.getValueType().getPyImports()
        yield "typing", "Dict"

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        return []

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        return []

    def addPair(self, key: str, allowomit: bool) -> None:
        self._keys.append((key, allowomit))

    def writepy(self, w: FileWriter) -> int:
        inner = ", ".join([f"{k!r}: {k}" for k, allowomit in self._keys if not allowomit])

        varstr = self._var.getPyExpr()[0]

        w.line0(f"{varstr}: {self._type.getQuotedPyType()} = {{{inner}}}")

        # now do the omittable args
        for k, allowomit in self._keys:
            if allowomit:
                # FIXME: this isn't how we want to do omitted args - we should be doing ellipsis
                expr = pannotomit(PanVar(k, None))
                w.line0(f"if {expr.getPyExpr()[0]}:")
                w.line1(f"{varstr}[{k!r}] = {k}")
        return 1

    def writets(self, w: FileWriter) -> None:
        inner = ", ".join([f"{k!r}: {k}" for k, allowomit in self._keys if not allowomit])

        varstr = self._var.getTSExpr()[0]

        w.line0(f"let {varstr}: {self._type.getTSType()[0]} = {{{inner}}};")

        # now do the omittable args
        for k, allowomit in self._keys:
            if allowomit:
                expr = pannotomit(PanVar(k, None))
                w.line0(f"if ({expr.getTSExpr()[0]}) {{")
                w.line1(f"{varstr}[{k!r}] = {k};")
                w.line0(f"}}")

    def writephp(self, w: FileWriter) -> None:
        # TODO: don't import this here
        from paradox.expressions import _phpstr

        phptype = self._type.getPHPTypes()[0]
        if phptype:
            w.line0(f"/** @var {phptype} */")

        inner = ", ".join(
            [_phpstr(k) + " => $" + k for k, allowomit in self._keys if not allowomit]
        )

        varstr = self._var.getPHPExpr()[0]

        w.line0(f"{varstr} = [{inner}];")

        # now do the omittable args
        for k, allowomit in self._keys:
            if allowomit:
                raise NotSupportedError("omittable args aren't supported by PHP")


class FunctionSpec(Statements):
    _rettype: Optional[CrossType]
    _isconstructor: bool = False

    @classmethod
    def _getconstructor(cls) -> "FunctionSpec":
        funcspec = cls(
            "__init__",
            "no_return",
            _ismethod=True,
        )
        funcspec._isconstructor = True
        return funcspec

    def __init__(
        self,
        name: str,
        returntype: Union[FlexiType, Literal["no_return"]],
        *,
        isasync: bool = False,
        docstring: List[str] = None,
        _isabstract: bool = False,
        _ismethod: bool = False,
        _isstaticmethod: bool = False,
    ) -> None:
        super().__init__()

        self._name = name

        if returntype == "no_return":
            # function declaration should have typescript "void" or python "None"
            self._rettype = None
        else:
            self._rettype = unflex(returntype)

        # list((name, type, default)))
        self._pargs: List[Tuple[str, CrossType, Optional[PanExpr]]] = []
        self._kwargs: List[Tuple[str, CrossType, Optional[PanExpr]]] = []
        self._overloads: List[FunctionSpec] = []
        self._decorators_py: List[str] = []
        self._decorators_ts: List[str] = []
        self._isabstract: bool = _isabstract
        self._ismethod: bool = _ismethod
        self._isstaticmethod: bool = _isstaticmethod
        self._isasync: bool = isasync
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
        overload._decorators_py.append("@typing.overload")
        overload._statements.append(PanExprStatement(pyexpr("...")))

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
        assert not len(self._overloads), "Added an arg after an overload was defined"

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

    def writepy(self, w: FileWriter) -> int:
        assert not self._isasync, "async FunctionSpec not yet supported in Python"

        # first write out overloads
        for overload in self._overloads:
            overload.writepy(w)

        # blank line
        w.blank()

        # decorators
        if self._isstaticmethod:
            w.line0("@classmethod")

        for dec in self._decorators_py:
            w.line0(dec)
        if self._isabstract:
            w.line0("@abc.abstractmethod")

        # header
        w.line0(f"def {self._name}(")

        if self._ismethod:
            w.line1("class_," if self._isstaticmethod else "self,")

        for argname, crosstype, argdefault in self._pargs:
            argstr = argname + ": " + crosstype.getQuotedPyType()
            if argdefault is not None:
                argstr += " = " + argdefault.getPyExpr()[0]
            w.line1(argstr + ",")
        if len(self._kwargs):
            # mark start of kwargs
            w.line1("*,")
        for argname, argtype, argdefault in self._kwargs:
            argstr = argname
            argstr += ": " + argtype.getQuotedPyType()
            if argdefault is not None:
                argstr += " = " + argdefault.getPyExpr()[0]
            w.line1(argstr + ",")

        if self._rettype is None:
            w.line0(f") -> None:")
        else:
            w.line0(f") -> {self._rettype.getQuotedPyType()}:")

        havebody = 0

        if self._docstring:
            w.line1('"""')
            for docline in self._docstring:
                w.line1(docline)
            w.line1('"""')
            havebody += 1

        for stmt in self._statements:
            havebody += stmt.writepy(w.with_more_indent())
            if self._isabstract:
                raise InvalidLogic(
                    f"Abstract FunctionSpec {self._name}() must not have any statements"
                )

        if not havebody:
            w.line1("..." if self._isabstract else "pass")

        return 1

    def writets(self, w: FileWriter) -> None:
        if self._docstring:
            w.line0("/**")
            for docline in self._docstring:
                w.line0(" * " + docline)
            w.line0(" */")

        modifiers: List[str] = []

        # TODO: do we need to write some imports?
        if self._isasync:
            assert not self._isconstructor, "async constructor not possible?"
            modifiers.append("async")

        if self._isabstract:
            if len(self._statements):
                raise InvalidLogic(
                    f"Abstract FunctionSpec {self._name}() must not have any statements"
                )

            modifiers.append("abstract")

        if self._isstaticmethod:
            modifiers.append("static")

        # first write out overloads
        if self._overloads:
            raise NotImplementedError("TypeScript overloads are not yet implemented")

        for decoration in self._decorators_ts:
            w.line0(decoration)

        if self._ismethod:
            if not len(modifiers):
                modifiers.append("public")
        else:
            modifiers.append("function")

        name = "constructor" if self._isconstructor else self._name
        w.line0((" ".join(modifiers)) + " " + name + "(")

        if self._kwargs:
            raise NotSupportedError("TypeScript does not support kwargs")

        # header
        for argname, crosstype, argdefault in self._pargs:
            argstr = argname + ": " + crosstype.getTSType()[0]
            if argdefault is not None:
                argstr += " = " + argdefault.getTSExpr()[0]
            w.line1(argstr + ",")

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
            w.line0(f"): {rettype};" if rettype else ");")
        else:
            w.line0(f"): {rettype} {{" if rettype else ") {")
            for stmt in self._statements:
                stmt.writets(w.with_more_indent())
            w.line0("}")

    def writephp(self, w: FileWriter) -> None:
        modifiers: List[str] = []

        assert not self._isasync, "PHP does not support async functions"

        if self._docstring:
            w.line0("/**")
            for docline in self._docstring:
                w.line0(" * " + docline)
            w.line0(" */")

        if self._isabstract:
            if len(self._statements):
                raise InvalidLogic(
                    f"Abstract FunctionSpec {self._name}() must not have any statements"
                )

            modifiers.append("abstract")

        if self._isstaticmethod:
            modifiers.append("static")

        # first write out overloads
        if self._overloads:
            raise NotSupportedError("PHP does not support overloads")

        if self._ismethod:
            modifiers.append("public")

        prefix = modifiers + ["function"]

        name = "__construct" if self._isconstructor else self._name
        w.line0((" ".join(prefix)) + " " + name + "(")

        if len(self._kwargs):
            raise NotSupportedError("PHP does not support kwargs")

        # header
        argnum = 0
        comma = ","
        for argname, crosstype, argdefault in self._pargs:
            argnum += 1
            if argnum == len(self._pargs):
                comma = ""
            argstr = "$" + argname
            phptype = crosstype.getPHPTypes()[0]
            if phptype:
                argstr = phptype + " " + argstr
            if argdefault is not None:
                argstr += " = " + argdefault.getPHPExpr()[0]
            w.line1(argstr + comma)

        rettype: str = ""
        if not self._isconstructor and self._rettype is not None:
            rettype = self._rettype.getPHPTypes()[0] or ""

        if rettype:
            rettype = ": " + rettype

        if self._isabstract:
            w.line0(f"){rettype};")
        else:
            w.line0(f"){rettype} {{")
            for stmt in self._statements:
                stmt.writephp(w.with_more_indent())
            w.line0("}")

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from super().getImportsPy()

        if self._isabstract:
            yield "abc", None
        for stmt in self._statements:
            yield from stmt.getImportsPy()

        crosstypes: List[CrossType] = [a[1] for a in itertools.chain(self._pargs, self._kwargs)]

        if self._rettype is not None:
            crosstypes.append(self._rettype)

        for crosstype in crosstypes:
            yield from crosstype.getPyImports()

        if self._overloads:
            yield "typing", None

        for overload in self._overloads:
            yield from overload.getImportsPy()

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


class ClassSpec(_StatementWithCustomImports):
    _pybases_args_kwargs: bool = False
    _phpbase: Optional[str] = None
    _tsbase: Optional[str] = None

    def __init__(
        self,
        name: str,
        *,
        docstring: List[str] = None,
        isabstract: bool = False,
        pydataclass: bool = False,
        tsexport: bool = False,
    ) -> None:
        super().__init__()

        self._name = name
        self._docstring = docstring
        self._isabstract = isabstract
        self._pydataclass = pydataclass
        self._propnames: Set[str] = set()

        self._methods: List[FunctionSpec] = []
        self._remarks: List[str] = []
        self._properties: List[ClassProperty] = []
        self._initargs: List[Tuple[str, CrossType, Optional[PanExpr]]] = []
        self._initdefaults: List[Tuple[str, PanExpr, CrossType]] = []
        self._decorators: List[str] = []
        self._tsexport: bool = tsexport
        self._pybases: List[str] = []

    @property
    def classname(self) -> str:
        return self._name

    def addPythonBaseClass(self, name: str, *, send_args_kwargs: bool = False) -> None:
        # TODO: I'm not super happy about this send_args_kwargs feature, but I've added it as a
        # short-term fix for backwards compatibility
        if send_args_kwargs:
            self._pybases_args_kwargs = True
        elif self._pybases_args_kwargs:
            # TODO: unit test this code path
            raise InvalidLogic("Cannot use send_args_kwargs=False and send_args_kwargs=True")

        self._pybases.append(name)

    def setPHPParentClass(self, name: str) -> None:
        if self._phpbase:
            raise InvalidLogic("Cannot add multiple PHP parent classes")
        self._phpbase = name

    def setTypeScriptParentClass(self, name: str) -> None:
        if self._tsbase:
            raise InvalidLogic("Cannot add multiple TypeScript parent classes")
        self._tsbase = name

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
            _isabstract=isabstract,
            _ismethod=True,
            _isstaticmethod=isstaticmethod,
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
        if name in self._propnames:
            raise InvalidLogic(
                f"Tried to add property {name} to ClassSpec {self._name} multiple times"
            )
        self._propnames.add(name)

        crosstype = unflex(type)
        realdefault = _pan_nodef(default)
        if initarg:
            self._initargs.append((name, crosstype, realdefault))
        elif realdefault is not None:
            self._initdefaults.append((name, realdefault, crosstype))

        self._properties.append(
            ClassProperty(
                propname=name,
                proptype=crosstype,
                propdefault=realdefault,
                tsobservable=tsobservable,
                tsreadonly=tsreadonly,
            )
        )
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

        initspec = FunctionSpec._getconstructor()
        for name, crosstype, pandefault in self._initargs:
            initspec.addPositionalArg(
                name,
                crosstype,
                default=NO_DEFAULT if pandefault is None else pandefault,
            )
            initspec.alsoAssign(PanProp(name, crosstype, None), PanVar(name, None))

        if self._pybases_args_kwargs and lang == "python":
            # TODO: unit test this code path
            initspec.addPositionalArg("*args", CrossAny())
            initspec.addPositionalArg("**kwargs", CrossAny())

        # also call parent class' init
        call_parent_constructor: Dict[str, Optional[str]] = {
            "php": None,
            "python": None,
            "typescript": None,
        }
        if self._pybases_args_kwargs:
            # TODO: unit test this code path
            call_parent_constructor["python"] = "super().__init__(*args, **kwargs)"
        elif self._pybases:
            call_parent_constructor["python"] = "super().__init__()"
        if self._tsbase:
            call_parent_constructor["typescript"] = "super();"
        if self._phpbase:
            call_parent_constructor["php"] = "parent::__construct();"
        initspec.also(HardCodedStatement(**call_parent_constructor))

        # do we need positional args for any of the properties?
        for name, default, crosstype in initdefaults:
            initspec.alsoAssign(PanProp(name, crosstype, None), default)

        return initspec

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from super().getImportsPy()
        if self._isabstract:
            yield "abc", None
        if self._pydataclass:
            yield "dataclasses", "dataclass"
        constructor = self._getInitSpec("python")
        if constructor:
            yield from constructor.getImportsPy()
        for prop in self._properties:
            yield from prop.proptype.getPyImports()
        for method in self._methods:
            yield from method.getImportsPy()

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        yield from self._importsts

        for prop in self._properties:
            # TODO: also need to yield imports from properties
            if prop.tsobservable:
                # TODO: unit test this code path
                yield "mobx", ["observable"]
                break
        constructor = self._getInitSpec("typescript")
        if constructor:
            yield from constructor.getImportsTS()
        for method in self._methods:
            yield from method.getImportsTS()

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        yield from super().getImportsPHP()

        # TODO: also need to yield imports from properties

        constructor = self._getInitSpec("php")
        if constructor:
            yield from constructor.getImportsPHP()
        for method in self._methods:
            yield from method.getImportsPHP()

    def remark(self, comment: str) -> None:
        self._remarks.append(comment)

    def writepy(self, w: FileWriter) -> int:
        havebody = False
        bases = self._pybases[:]

        # write out class header
        if self._isabstract:
            bases.append("abc.ABC")
        if self._pydataclass:
            w.line0("@dataclass")

        parents = ", ".join(bases)
        if parents:
            parents = "(" + parents + ")"
        w.line0(f"class {self._name}{parents}:")
        if self._docstring:
            w.line1('"""')
            for docline in self._docstring:
                w.line1(docline.strip())
            w.line1('"""')
            w.blank()
            havebody = True

        # first write out properties
        for prop in self._properties:
            w.line1(f"{prop.propname}: {prop.proptype.getQuotedPyType()}")
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
            w.line1("# " + comment)
            w.blank()

        if not havebody:
            w.line1("pass")

        return 1

    def writets(self, w: FileWriter) -> None:
        if self._docstring:
            w.line0("/**")
            for docline in self._docstring:
                w.line0(" * " + docline)
            w.line0(" */")

        prefix = ""
        if self._tsexport:
            prefix = "export "

        if self._isabstract:
            prefix += "abstract "

        extends = ""
        if self._tsbase:
            extends = f" extends {self._tsbase}"

        w.line0(f"{prefix}class {self._name}{extends} {{")

        needemptyline = False

        # first write out properties
        for prop in self._properties:
            if prop.tsobservable:
                w.blank()
                w.line1(f"@observable")
            if prop.tsreadonly:
                prefix = "readonly "
            else:
                prefix = "public "
            assign = ""

            # only assign values in the class body if the value is a literal
            if prop.propdefault and isinstance(prop.propdefault, PanLiteral):
                assign = " = " + prop.propdefault.getTSExpr()[0]

            w.line1(f"{prefix}{prop.propname}: {prop.proptype.getTSType()[0]}{assign};")
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
            w.line1("// " + comment)
            w.blank()

        w.line0("}")

    def writephp(self, w: FileWriter) -> None:
        prefix = ""

        if self._isabstract:
            prefix += "abstract "

        if self._docstring:
            w.line0("/**")
            for docline in self._docstring:
                w.line0(" * " + docline.strip())
            w.line0(" */")

        extends = ""
        if self._phpbase:
            extends = " extends " + self._phpbase

        w.line0(f"{prefix}class {self._name}{extends} {{")

        needemptyline = False

        # first write out properties
        for prop in self._properties:
            assign = ""

            # only assign values in the class body if the value is a literal
            if prop.propdefault and isinstance(prop.propdefault, PanLiteral):
                assign = " = " + prop.propdefault.getPHPExpr()[0]

            phptypes = prop.proptype.getPHPTypes()
            w.line1(f"/** @var {phptypes[1]} */")
            w.line1(f"public ${prop.propname}{assign};")
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
                w.line1("// " + comment)
                w.blank()

        w.line0("}")


class InterfaceSpec(_StatementWithCustomImports):
    def __init__(
        self,
        name: str,
        *,
        tsexport: bool = False,
    ) -> None:
        super().__init__()

        self._name = name
        self._properties: List[Tuple[str, CrossType]] = []
        self._tsexport: bool = tsexport

    def addProperty(
        self,
        name: str,
        type: FlexiType,
    ) -> None:
        self._properties.append((name, unflex(type)))

    def getImportsPy(self) -> Iterable[ImportSpecPy]:
        yield from super().getImportsPy()
        for _, crosstype in self._properties:
            yield from crosstype.getPyImports()

    def getImportsPHP(self) -> Iterable[ImportSpecPHP]:
        yield from super().getImportsPHP()
        for _, crosstype in self._properties:
            yield from crosstype.getImportsPHP()

    def getImportsTS(self) -> Iterable[ImportSpecTS]:
        yield from super().getImportsTS()
        # TODO: make sure this is unit tested
        for name, crosstype in self._properties:
            # TODO: get imports from crosstype
            # yield from crosstype.getImportsTS()
            pass
        return []

    def writepy(self, w: FileWriter) -> int:
        raise NotSupportedError("InterfaceSpec can't generate python code")

    def writets(self, w: FileWriter) -> None:
        export = "export " if self._tsexport else ""
        w.line0(f"{export}interface {self._name} {{")
        for propname, proptype in self._properties:
            w.line1(f"{propname}: {proptype.getTSType()[0]};")
        w.line0(f"}}")

    def writephp(self, w: FileWriter) -> None:
        w.line0(f"interface {self._name} {{")
        # FIXME: PHP doesn't support properties in interfaces, so maybe this
        # feature isn't so useful in its current form
        w.line0(f"}}")
