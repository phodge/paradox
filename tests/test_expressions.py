from paradox.expressions import PanLiteral


def test_PanLiteral() -> None:
    assert PanLiteral(True).getPHPExpr()[0] == 'true'
    assert PanLiteral(True).getPyExpr()[0] == 'True'
    assert PanLiteral(True).getTSExpr()[0] == 'true'
    assert PanLiteral(False).getPHPExpr()[0] == 'false'
    assert PanLiteral(False).getPyExpr()[0] == 'False'
    assert PanLiteral(False).getTSExpr()[0] == 'false'
    assert PanLiteral(0).getPHPExpr()[0] == '0'
    assert PanLiteral(0).getPyExpr()[0] == '0'
    assert PanLiteral(0).getTSExpr()[0] == '0'
    assert PanLiteral(1250).getPHPExpr()[0] == '1250'
    assert PanLiteral(1250).getPyExpr()[0] == '1250'
    assert PanLiteral(1250).getTSExpr()[0] == '1250'
    assert PanLiteral(-912343).getPHPExpr()[0] == '-912343'
    assert PanLiteral(-912343).getPyExpr()[0] == '-912343'
    assert PanLiteral(-912343).getTSExpr()[0] == '-912343'
    assert PanLiteral('').getPHPExpr()[0] == "''"
    assert PanLiteral('').getPyExpr()[0] == "''"
    assert PanLiteral('').getTSExpr()[0] == "''"
    assert PanLiteral('\'').getPHPExpr()[0] == "'\\''"
    assert PanLiteral('\'').getPyExpr()[0] == '"\'"'
    assert PanLiteral('\'').getTSExpr()[0] == '"\'"'
    assert PanLiteral('0').getPHPExpr()[0] == "'0'"
    assert PanLiteral('0').getPyExpr()[0] == "'0'"
    assert PanLiteral('0').getTSExpr()[0] == "'0'"
