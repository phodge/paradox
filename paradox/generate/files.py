import abc
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from paradox.output import Script

# imported for backwards-compatibility
# isort: off
from paradox.output import FileWriter  # noqa: F401

if TYPE_CHECKING:
    from paradox.typing import CrossType


class FileSpec(abc.ABC):
    def __init__(self, target: Path) -> None:
        self.target: Path = target
        self.contents = Script()

    def filecomment(self, text: str) -> None:
        self.contents.add_file_comment(text)

    def getfirstline(self) -> Optional[str]:
        if not self.target.exists():
            return None

        with self.target.open() as f:
            return f.readline()

    def add_new_type(self, name: str, base: "CrossType", *, tsexport: bool = False) -> None:
        self.contents.add_new_type(name, base, tsexport=tsexport)

    @abc.abstractmethod
    def writefile(self) -> None:
        ...

    @abc.abstractmethod
    def makepretty(self) -> None:
        ...


class FilePython(FileSpec):
    def writefile(self) -> None:
        self.contents.write_to_path(self.target, lang="python")

    def makepretty(self) -> None:
        subprocess.check_call(["isort", self.target])
        # TODO: standardise these parameters somewhere
        subprocess.check_call(["black", "--target-version=py37", "--line-length=98", self.target])


class FileTS(FileSpec):
    def __init__(self, target: Path, *, npmroot: Path):
        super().__init__(target)

        self.npmroot: Path = npmroot

    def writefile(self, indentstr: str = "  ") -> None:
        self.contents.write_to_path(
            self.target,
            lang="typescript",
            # for backwards compatibility with old versions
            indentstr="  ",
        )

    def makepretty(self) -> None:
        # sort imports
        # TODO: work out if it's worthwhile getting an import sorter happening for this project
        if False:
            subprocess.check_call(
                ["npx", "import-sort", "--write", self.target.absolute()],
                cwd=self.npmroot,
            )

        # TODO: use "prettier" to format the file, maybe
        pass


class FilePHP(FileSpec):
    def __init__(self, target: Path, *, namespace: str = None) -> None:
        super().__init__(target)

        self._namespace = namespace

    def writefile(self) -> None:
        self.contents.write_to_path(
            self.target,
            lang="php",
            phpnamespace=self._namespace,
            # for backwards compatibility with old versions
            indentstr="  ",
        )

    def makepretty(self) -> None:
        # TODO: run php-cs-fixer over the file to format it correctly
        pass
