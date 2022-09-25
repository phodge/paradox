from textwrap import dedent

from _paradoxtest import SupportedLang
from paradox.expressions import PanCall, pan
from paradox.generate.statements import NO_DEFAULT, ClassSpec
from paradox.output import Script
from paradox.typing import CrossAny, dictof, listof, lit, unionof


def test_ClassSpec(LANG: SupportedLang) -> None:
    s = Script()

    c = s.also(
        ClassSpec(
            "Class1",
            docstring=["A", "Wicked", "Cool", "Class"],
        )
    )
    c.addProperty("prop1", str, default="why?")
    prop2 = c.addProperty("prop2", int, default=79, initarg=True)

    # create a Factory method
    factoryfn = c.createMethod("sixtysix", CrossAny(), isstaticmethod=True)
    factoryfn.alsoReturn(PanCall.callClassConstructor("Class1", pan(66)))

    # other method with body
    getprop2 = c.createMethod(
        "getprop2",
        unionof(str, lit(-1)),
        docstring=["Return prop2,", "or -1 if it is empty"],
    )
    with getprop2.withCond(prop2) as cond:
        cond.alsoReturn(prop2)
    getprop2.alsoReturn(pan(-1))

    source_code = s.get_source_code(lang=LANG)

    if LANG == "php":
        expected = """
            <?php

            /**
             * A
             * Wicked
             * Cool
             * Class
             */
            class Class1 {
                /** @var string */
                public $prop1 = 'why?';
                /** @var int */
                public $prop2 = 79;

                public function __construct(
                    int $prop2 = 79
                ) {
                    $this->prop2 = $prop2;
                }

                static public function sixtysix(
                ) {
                    return new Class1(66);
                }

                /**
                 * Return prop2,
                 * or -1 if it is empty
                 */
                public function getprop2(
                ) {
                    if ($this->prop2) {
                        return $this->prop2;
                    }

                    return -1;
                }
            }
            """
    elif LANG == "python":
        expected = '''
            import typing
            import typing_extensions

            class Class1:
                """
                A
                Wicked
                Cool
                Class
                """

                prop1: str
                prop2: int


                def __init__(
                    self,
                    prop2: int = 79,
                ) -> None:
                    self.prop2 = prop2
                    self.prop1 = 'why?'


                @classmethod
                def sixtysix(
                    class_,
                ) -> typing.Any:
                    return Class1(66)


                def getprop2(
                    self,
                ) -> typing.Union[str, typing_extensions.Literal[-1]]:
                    """
                    Return prop2,
                    or -1 if it is empty
                    """
                    if self.prop2:
                        return self.prop2

                    return -1

            '''
    else:
        assert LANG == "typescript"
        expected = """
            /**
             * A
             * Wicked
             * Cool
             * Class
             */
            class Class1 {
                public prop1: string = 'why?';
                public prop2: number = 79;

                public constructor(
                    prop2: number = 79,
                ) {
                    this.prop2 = prop2;
                }

                static sixtysix(
                ): any {
                    return new Class1(66);
                }

                /**
                 * Return prop2,
                 * or -1 if it is empty
                 */
                public getprop2(
                ): string | -1 {
                    if (this.prop2) {
                        return this.prop2;
                    }

                    return -1;
                }
            }
            """

    assert source_code == dedent(expected).lstrip()
    assert c.classname == "Class1"


def test_ClassSpec_abstract(LANG: SupportedLang) -> None:
    s = Script()

    c = s.also(
        ClassSpec(
            "Class2",
            isabstract=True,
        )
    )
    c.addProperty("meta1", int, default=NO_DEFAULT)
    am = c.createMethod("abstract_method", unionof(str, int), isabstract=True)
    am.addPositionalArg("a", listof(int))
    am.addPositionalArg("b", dictof(int, bool))

    source_code = s.get_source_code(lang=LANG)

    if LANG == "php":
        expected = """
            <?php

            abstract class Class2 {
                /** @var int */
                public $meta1;

                abstract public function abstract_method(
                    array $a,
                    array $b
                );
            }
            """
    elif LANG == "python":
        expected = """
            import abc
            import typing

            class Class2(abc.ABC):
                meta1: int


                @abc.abstractmethod
                def abstract_method(
                    self,
                    a: typing.List[int],
                    b: typing.Dict[int, bool],
                ) -> typing.Union[str, int]:
                    ...

            """
    else:
        assert LANG == "typescript"
        expected = """
            abstract class Class2 {
                public meta1: number;

                abstract abstract_method(
                    a: number[],
                    b: {[k: number]: boolean},
                ): string | number;
            }
            """

    assert source_code == dedent(expected).lstrip()
    assert c.classname == "Class2"
