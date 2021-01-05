import io

import pytest


def test_generate_interface_spec() -> None:
    from paradox.generate.files import FileWriter
    from paradox.generate.statements import InterfaceSpec
    from paradox.typing import CrossBool

    spec = InterfaceSpec('Window')
    spec.addProperty('closed', CrossBool())

    # Note that InterfaceSpec doesn't yet support methods

    # FIXME: we generate the interface but don't actually check its contents
    spec.writets(FileWriter(io.StringIO(), '  '))

    # this will probably never be implemented
    with pytest.raises(NotImplementedError):
        spec.writepy(FileWriter(io.StringIO(), '  '))

    # this is not implemented yet
    with pytest.raises(NotImplementedError):
        spec.writephp(FileWriter(io.StringIO(), '  '))
