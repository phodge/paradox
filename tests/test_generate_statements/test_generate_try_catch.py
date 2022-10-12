from textwrap import dedent

from _paradoxtest import SupportedLang
from paradox.expressions import PanCall, PanVar, pan
from paradox.output import Script


def test_generate_try_catch(LANG: SupportedLang) -> None:
    s = Script()

    with s.withTryBlock() as tryblock:
        tryblock.also(PanCall("do_something", pan("some text")))
        tryblock.alsoRaise("SomeException", msg="some message")

        v_e = PanVar("e", None)
        with tryblock.withCatchBlock2(
            None,
            phpclass="SomeException",
            pyclass="SomeException",
            tsclass="SomeException",
        ) as catchblock:
            catchblock.also(PanCall("alt_behaviour_1"))
        with tryblock.withCatchBlock2(
            v_e, phpclass="LogicException", pyclass="LogicException", tsclass="LogicException",
        ) as catchblock:
            catchblock.also(PanCall("log_something_bad", v_e))
        with tryblock.withCatchBlock2() as catchblock:
            catchblock.remark("XXX: ignore silently for now")
        with tryblock.withFinallyBlock() as finallyblock:
            finallyblock.also(PanCall("do_cleanup"))

    # TODO: would be good to ensure that python puts 'pass' into an empty
    # finally block

    # TODO: would be good to ensure that a try/except with no contents raises
    # InvalidLogic

    if LANG == "php":
        expected = dedent(
            """
            <?php

            try {
                do_something('some text');
                throw new SomeException('some message');
            } catch (SomeException $_) {
                alt_behaviour_1();
            } catch (LogicException $e) {
                log_something_bad($e);
            } catch (Exception $_) {
                // XXX: ignore silently for now
            } finally {
                do_cleanup();
            }
            """
        ).lstrip()
    elif LANG == "python":
        expected = dedent(
            """
            try:
                do_something('some text')
                raise SomeException('some message')
            except SomeException:
                alt_behaviour_1()
            except LogicException as e:
                log_something_bad(e)
            except Exception:
                # XXX: ignore silently for now
                pass
            finally:
                do_cleanup()
            """
        ).lstrip()
    else:
        assert LANG == "typescript"
        expected = dedent(
            """
            try {
                do_something('some text');
                throw new SomeException('some message');
            } catch (e) {
                if (e instanceof SomeException) {
                    alt_behaviour_1();
                } else if (e instanceof LogicException) {
                    log_something_bad(e);
                } else {
                    // XXX: ignore silently for now
                }
            } finally {
                do_cleanup();
            }
            """
        ).lstrip()

    assert s.get_source_code(lang=LANG) == expected
