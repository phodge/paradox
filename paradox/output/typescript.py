from collections import defaultdict
from typing import Dict, List, Optional, Set

from paradox.interfaces import DefinesCustomTypes, WantsImports
from paradox.output import FileWriter


def write_file_comments(writer: FileWriter, comments: List[str]) -> None:
    for comment in comments:
        if len(comment):
            writer.line0(f"// {comment}")
        else:
            writer.line0("//")


def write_top_imports(writer: FileWriter, top: WantsImports) -> None:
    # group imports by source module so that we can remove duplicates
    imports_by_module: Dict[str, Set[Optional[str]]] = defaultdict(set)
    for module, names in top.getImportsTS():
        if names is None:
            imports_by_module[module].add(None)
        else:
            imports_by_module[module].update(names)

    # next, write out imports
    for module, names2 in imports_by_module.items():
        strnames = set()
        for name in names2:
            if name is None:
                writer.line0(f"import '{module}';")
            else:
                strnames.add(name)
        for name in sorted(strnames):
            writer.line0(f"import {{{name}}} from '{module}';")
    if len(imports_by_module):
        writer.blank()


def write_custom_types(writer: FileWriter, top: DefinesCustomTypes) -> None:
    havenewtypes = False
    for newtype, crossbase, export in top.getTypesTS():
        havenewtypes = True
        prefix = ''
        if export:
            prefix = 'export '
        tstype = crossbase.getTSType()[0]
        writer.line0(prefix + f"type {newtype} = {tstype} & {{readonly brand: unique symbol}};")
    if havenewtypes:
        writer.blank()
