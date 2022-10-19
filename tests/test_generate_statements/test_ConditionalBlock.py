from textwrap import dedent

from _paradoxtest import SupportedLang
from paradox.expressions import pan
from paradox.output import Script
from paradox.typing import CrossAny


def test_ConditionalBlock(LANG: SupportedLang) -> None:
    s = Script()

    with s.withCond(pan(True)) as cond:
        v_result = cond.alsoDeclare("result", CrossAny(), pan(55))

    with s.withCond(pan(2)) as cond:
        cond.alsoAssign(v_result, pan(56))
        with cond.withElseif(pan(3)) as cond2:
            cond2.alsoAssign(v_result, pan(57))

    with s.withCond(pan(4)) as cond:
        cond.alsoAssign(v_result, pan(58))
        with cond.withElseif(pan(5)) as cond2:
            cond2.alsoAssign(v_result, pan(59))
        with cond.withElseif(pan(6)) as cond2:
            # test an empty elseif block
            cond2.remark("Nothing to see here")
            pass
        with cond.withElseif(pan(7)) as cond2:
            # test a nested if/else block
            with cond2.withCond(pan(8)) as cond3:
                cond3.alsoAssign(v_result, pan(60))
                with cond3.withElse() as else_:
                    else_.alsoAssign(v_result, pan(61))
        with cond.withElse() as else_:
            else_.alsoDeclare(v_result, "no_type", pan(62))

    source_code = s.get_source_code(lang=LANG)

    if LANG == "php":
        expected = """
            <?php

            if (true) {
                /** @var mixed */
                $result = 55;
            }

            if (2) {
                $result = 56;
            } elseif (3) {
                $result = 57;
            }

            if (4) {
                $result = 58;
            } elseif (5) {
                $result = 59;
            } elseif (6) {
                // Nothing to see here
            } elseif (7) {
                if (8) {
                    $result = 60;
                } else {
                    $result = 61;
                }

            } else {
                /** @var mixed */
                $result = 62;
            }

            """
    elif LANG == "python":
        expected = """
            from typing import Any

            if True:
                result: Any = 55

            if 2:
                result = 56
            elif 3:
                result = 57

            if 4:
                result = 58
            elif 5:
                result = 59
            elif 6:
                # Nothing to see here
                pass
            elif 7:
                if 8:
                    result = 60
                else:
                    result = 61

            else:
                result: Any = 62

            """
    else:
        assert LANG == "typescript"
        expected = """
            if (true) {
                let result: any = 55;
            }

            if (2) {
                result = 56;
            } else if (3) {
                result = 57;
            }

            if (4) {
                result = 58;
            } else if (5) {
                result = 59;
            } else if (6) {
                // Nothing to see here
            } else if (7) {
                if (8) {
                    result = 60;
                } else {
                    result = 61;
                }

            } else {
                let result: any = 62;
            }

            """
    assert source_code == dedent(expected).lstrip()
