from paradox.interfaces import AcceptsStatements


def _add_statements(s: AcceptsStatements) -> None:
    pass  # TODO: use all features of AcceptsStatements


def test_implements_AcceptsStatements() -> None:
    from paradox.output import Script

    s = Script()
    _add_statements(s)

    # TODO: test generated code
