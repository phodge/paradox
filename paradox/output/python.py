from collections import defaultdict
from typing import Dict, List, Set

from paradox.interfaces import WantsImports
from paradox.output import FileWriter, Script


def write_file_comments(writer: FileWriter, comments: List[str]) -> None:
    writer.line0('"""')
    for comment in comments:
        writer.line0(comment)
    writer.line0('"""')


def write_top_imports(writer: FileWriter, *, top: WantsImports, script: Script) -> None:
    # group imports first
    direct_imports: Set[str] = set()
    named_imports: Dict[str, Set[str]] = defaultdict(set)
    for module, name in top.getImportsPy():
        if name is None:
            direct_imports.add(module)
        else:
            named_imports[module].add(name)

    for newtype in script._new_types.values():
        named_imports["typing"].add("NewType")
        for module, name in newtype.base.getPyImports():
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


def write_custom_types(writer: FileWriter, script: Script) -> None:
    count = 0
    for newtype in script._new_types.values():
        pytype = newtype.base.getPyType()[0]
        name = newtype.name
        writer.line0(f"{name} = NewType({name!r}, {pytype})")
        count += 1
    if count:
        writer.blank()
