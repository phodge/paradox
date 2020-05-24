import abc
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import IO
from typing import Dict, List, Optional, Set


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
        indentstr = ''
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


class FileSpec(abc.ABC):
    def __init__(self, target: Path) -> None:
        from paradox.generate.statements import Statements

        self.target: Path = target
        self.contents: Statements = Statements()
        self._filecomments: List[str] = []

    def filecomment(self, text: str) -> None:
        self._filecomments.append(text)

    def getfirstline(self) -> Optional[str]:
        if not self.target.exists():
            return None

        with self.target.open() as f:
            return f.readline()

    @abc.abstractmethod
    def writefile(self) -> None: ...

    @abc.abstractmethod
    def makepretty(self) -> None: ...


class FilePython(FileSpec):
    def writefile(self) -> None:
        with self.target.open('w') as f:
            # first, write out any file header
            if len(self._filecomments):
                f.write('"""\n')
                for text in self._filecomments:
                    f.write(text + "\n")
                f.write('"""\n')

            for module, names in self.contents.getImportsPy():
                if names is None:
                    f.write(f"import {module}\n")
                else:
                    f.write(f"from {module} import {', '.join(names)}\n")

            self.contents.writepy(FileWriter(f, '    '))

    def makepretty(self) -> None:
        subprocess.check_call(['isort', self.target])
        # TODO: standardise these parameters somewhere
        subprocess.check_call(['black', '--target-version=py37', '--line-length=98', self.target])


class FileTS(FileSpec):
    def __init__(self, target: Path, *, npmroot: Path):
        super().__init__(target)

        self.npmroot: Path = npmroot

    def writefile(self) -> None:
        # group imports by source module so that we can remove duplicates
        imports_by_module: Dict[str, Set[Optional[str]]] = defaultdict(set)
        for module, names in self.contents.getImportsTS():
            if names is None:
                imports_by_module[module].add(None)
            else:
                imports_by_module[module].update(names)

        with self.target.open('w') as f:
            # first, write out any file header
            for text in self._filecomments:
                f.write(f"// {text}\n")

            # next, write out imports
            for module, names2 in imports_by_module.items():
                if None in names2:
                    f.write(f"import '{module}';\n")
                    names2.remove(None)
                for name in sorted(names2):
                    f.write(f"import {{{name}}} from '{module}';\n")
            if len(imports_by_module):
                f.write("\n")

            # next, write out custom types
            havenewtypes = False
            for newtype, crossbase, export in self.contents.getTypesTS():
                havenewtypes = True
                if export:
                    f.write('export ')
                tstype = crossbase.getTSType()[0]
                f.write(f"type {newtype} = {tstype} & {{readonly brand: unique symbol}};\n")
            if havenewtypes:
                f.write("\n")

            self.contents.writets(FileWriter(f, '  '))

    def makepretty(self) -> None:
        # sort imports
        # TODO: work out if it's worthwhile getting an import sorter happening for this project
        if False:
            subprocess.check_call(
                ['npx', 'import-sort', '--write', self.target.absolute()],
                cwd=self.npmroot,
            )

        # TODO: use "prettier" to format the file, maybe
        pass
