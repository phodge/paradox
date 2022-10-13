from typing import Dict, List, Optional

from paradox.interfaces import WantsImports
from paradox.output import FileWriter, Script


def write_file_comments(writer: FileWriter, comments: List[str]) -> None:
    for text in comments:
        if len(text):
            writer.line0(f"// {text}")
        else:
            writer.line0("//")
    if len(comments):
        writer.blank()


def write_top_imports(writer: FileWriter, *, top: WantsImports, script: Script) -> None:
    # group imports by source module so that we can sort them
    imports: Dict[str, Optional[str]] = {}
    for original, alias in top.getImportsPHP():
        try:
            assert imports[original] == alias
        except KeyError:
            imports[original] = alias

    # next, write out imports
    wroteimports = False
    for original, alias in sorted(imports.items()):
        if alias:
            writer.line0(f"use {original} as {alias};")
        else:
            writer.line0(f"use {original};")
        wroteimports = True
    if wroteimports:
        writer.blank()


def write_custom_types(writer: FileWriter, script: Script) -> None:
    # PHP doesn't support custom types
    pass
