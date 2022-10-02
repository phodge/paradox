import io
from contextlib import contextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Iterator, List, Optional, Union

from typing_extensions import Literal

from paradox.interfaces import AcceptsStatements, AlsoParam

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
        TryCatchBlock,
    )
    from paradox.typing import FlexiType


class FileWriter:
    def __init__(
        self,
        f: IO[str],
        indentstr: str,
        baseindent: int = 0,
    ) -> None:
        self._f = f
        self._indentstr: str = indentstr
        self._baseindent: int = baseindent

    def _wline(self, indent: int, line: str) -> None:
        # when indent is -1, always write with no indent
        indentstr = ""
        if indent != -1:
            indentstr = self._indentstr * (indent + self._baseindent)
        self._f.write(indentstr + line + "\n")

    def line0(self, line: str) -> None:
        self._wline(0, line)

    def line1(self, line: str) -> None:
        self._wline(1, line)

    def blank(self) -> None:
        self._f.write("\n")

    def with_more_indent(self) -> "FileWriter":
        return FileWriter(self._f, self._indentstr, self._baseindent + 1)


class Script(AcceptsStatements):
    def __init__(self) -> None:
        from paradox.generate.statements import Statements

        super().__init__()

        # TODO: can we just hold a list of Statements directly? Note this means we would need to
        # implement WantsImports as well
        self._content = Statements()
        self._file_comments: List[str] = []

    def add_file_comment(self, text: str) -> None:
        """Supercedes the old FileSpec.filecomment()"""
        self._file_comments.append(text)

    def also(self, stmt: AlsoParam) -> AlsoParam:
        return self._content.also(stmt)

    def blank(self) -> None:
        self._content.blank()

    def remark(self, text: str) -> None:
        self._content.remark(text)

    def alsoImportPy(self, module: str, names: List[str] = None) -> None:
        self._content.alsoImportPy(module, names)

    def alsoImportTS(self, module: str, names: List[str] = None) -> None:
        self._content.alsoImportTS(module, names)

    def alsoAppend(self, list_: "Pannable", value: "Pannable") -> None:
        self._content.alsoAppend(list_, value)

    def alsoRaise(self, ctor: str = None, *, msg: str = None, expr: "PanExpr" = None) -> None:
        self._content.alsoRaise(ctor, msg=msg, expr=expr)

    def alsoAssign(
        self,
        var: "Union[PanVar, PanIndexAccess, PanKeyAccess]",
        expr: "Pannable",
    ) -> None:
        self._content.alsoAssign(var, expr)

    def alsoDeclare(
        self,
        target: "Union[str, PanVar]",
        type: "Union[None, FlexiType, Literal['no_type']]",
        value: "Union[Pannable, builtins.ellipsis]" = ...,
    ) -> "PanVar":
        return self._content.alsoDeclare(target, type, value)

    @contextmanager
    def withTryBlock(self) -> "Iterator[TryCatchBlock]":
        with self._content.withTryBlock() as b:
            yield b

    @contextmanager
    def withCond(self, expr: "PanExpr") -> "Iterator[ConditionalBlock]":
        with self._content.withCond(expr) as cond:
            yield cond

    @contextmanager
    def withFor(
        self,
        assign: "PanVar",
        expr: "Pannable",
    ) -> "Iterator[ForLoopBlock]":
        with self._content.withFor(assign, expr) as loop:
            yield loop

    @contextmanager
    def withDictIter(
        self,
        v_dict: "PanExpr",
        v_val: "PanVar",
        v_key: "PanVar" = None,
    ) -> "Iterator[DictLoopBlock]":
        with self._content.withDictIter(v_dict, v_val, v_key) as loop:
            yield loop

    def write_to_path(
        self,
        target: Path,
        *,
        lang: str,
        indentstr: str = "    ",
        pretty: bool = False,
        phpnamespace: str = None,
    ) -> None:
        # TODO: add a targetversion arg which can be used to do things like choose a target
        # language version (e.g. lang="php", targetversion="3.7")
        with target.open("w") as f:
            writer = FileWriter(f, indentstr=indentstr)
            self._write_to_writer(writer, lang=lang, pretty=pretty, phpnamespace=phpnamespace)

    def write_to_handle(
        self,
        handle: IO[str],
        *,
        lang: str,
        indentstr: str = "    ",
        pretty: bool = False,
        phpnamespace: str = None,
    ) -> None:
        # TODO: add a targetversion arg which can be used to do things like choose a target
        # language version (e.g. lang="php", targetversion="3.7")
        writer = FileWriter(handle, indentstr=indentstr)

        self._write_to_writer(writer, lang=lang, pretty=pretty, phpnamespace=phpnamespace)

    def get_source_code(
        self,
        *,
        lang: str,
        indentstr: str = "    ",
        pretty: bool = False,
        phpnamespace: str = None,
    ) -> str:
        # TODO: add a targetversion arg which can be used to do things like choose a target
        # language version (e.g. lang="php", targetversion="3.7")
        if pretty:
            raise NotImplementedError("Cannot prettify in-memory")

        handle = io.StringIO()
        writer = FileWriter(handle, indentstr=indentstr)

        self._write_to_writer(writer, lang=lang, pretty=pretty, phpnamespace=phpnamespace)

        handle.seek(0)
        return handle.read()

    def _write_to_writer(
        self,
        writer: FileWriter,
        *,
        lang: str,
        pretty: bool,
        phpnamespace: Optional[str],
    ) -> None:
        if pretty:
            raise NotImplementedError("Prettifying is not yet supported")

        if lang == "php":
            from paradox.output import php

            write_file_comments = php.write_file_comments
            write_top_imports = php.write_top_imports
            write_custom_types = php.write_custom_types

            writer.line0("<?php")
            writer.blank()
        elif lang == "python":
            from paradox.output import python

            write_file_comments = python.write_file_comments
            write_top_imports = python.write_top_imports
            write_custom_types = python.write_custom_types
        else:
            assert lang == "typescript"
            from paradox.output import typescript

            write_file_comments = typescript.write_file_comments
            write_top_imports = typescript.write_top_imports
            write_custom_types = typescript.write_custom_types

        # first, write out any file header
        if self._file_comments:
            write_file_comments(writer, self._file_comments)

        # if php, might need to write a PHP namespace
        if lang == "php" and phpnamespace:
            writer.line0(f"namespace {phpnamespace};")
            writer.blank()

        write_top_imports(writer, self._content)

        write_custom_types(writer, self._content)

        if lang == "php":
            self._content.writephp(writer)
        elif lang == "python":
            self._content.writepy(writer)
        else:
            assert lang == "typescript"
            self._content.writets(writer)
