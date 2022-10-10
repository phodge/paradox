from collections import defaultdict
from typing import Dict, List, Set

from paradox.interfaces import DefinesCustomTypes, WantsImports
from paradox.output import FileWriter


def write_file_comments(writer: FileWriter, comments: List[str]) -> None:
    writer.line0('"""')
    for comment in comments:
        writer.line0(comment)
    writer.line0('"""')


def write_top_imports(writer: FileWriter, top: WantsImports) -> None:
    # group imports first
    direct_imports: Set[str] = set()
    named_imports: Dict[str, Set[str]] = defaultdict(set)
    for module, name in top.getImportsPy():
        if name is None:
            direct_imports.add(module)
        else:
            named_imports[module].add(name)

    for name in sorted(direct_imports):
        writer.line0(f"import {name}")
    if direct_imports:
        writer.blank()

    for module, imported_names in sorted(named_imports.items(), key=lambda pair: pair[0]):
        writer.line0(f"from {module} import {', '.join(sorted(imported_names))}")
    if named_imports:
        writer.blank()


def write_custom_types(writer: FileWriter, top: DefinesCustomTypes) -> None:
    for name, crossbase in top.getTypesPy():
        raise NotImplementedError("TODO: implement this")
