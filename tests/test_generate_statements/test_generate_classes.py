from textwrap import dedent

import pytest

from _paradoxtest import SupportedLang
from paradox.expressions import PanCall, pan
from paradox.generate.statements import NO_DEFAULT, ClassSpec
from paradox.interfaces import InvalidLogic
from paradox.output import Script
from paradox.typing import (
    CrossCustomType,
    CrossNull,
    dictof,
    listof,
    lit,
    maybe,
    unionof,
)


def test_ClassSpec(LANG: SupportedLang) -> None:
    # TODO: add tests for the following ClassSpec features
    # .createMethod()
    #   isasync
    s = Script()

    c = s.also(
        ClassSpec(
            "Class1",
            docstring=["A", "Wicked", "Cool", "Class"],
        )
    )
    c.remark("This comment will appear at the end")
    c.addProperty("prop1", str, default="why?")
    prop2 = c.addProperty("prop2", int, default=79, initarg=True)

    # create a Factory method
    factoryfn = c.createMethod(
        "sixtysix",
        CrossCustomType(python="Class1", typescript="Class1", phplang="Class1", phpdoc="Class1"),
        isstaticmethod=True,
    )
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
                ): Class1 {
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
                // This comment will appear at the end

            }
            """
    elif LANG == "python":
        expected = '''
            from typing import Literal, Union

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
                ) -> 'Class1':
                    return Class1(66)


                def getprop2(
                    self,
                ) -> Union[str, Literal[-1]]:
                    """
                    Return prop2,
                    or -1 if it is empty
                    """
                    if self.prop2:
                        return self.prop2

                    return -1

                # This comment will appear at the end

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
                ): Class1 {
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
                // This comment will appear at the end

            }
            """

    assert source_code == dedent(expected).lstrip()
    assert c.classname == "Class1"


def test_ClassSpec_cannot_add_same_prop_multiple_times(LANG: SupportedLang) -> None:
    c = ClassSpec("SomeClass")
    c.addProperty("some_prop", str)
    with pytest.raises(InvalidLogic):
        c.addProperty("some_prop", str)


def test_ClassSpec_abstract(LANG: SupportedLang) -> None:
    s = Script()

    c = s.also(
        ClassSpec(
            "Class2",
            isabstract=True,
        )
    )
    # TODO: NO_DEFAULT probably belongs in paradox.interfaces or even root paradox
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

            from typing import Dict, List, Union

            class Class2(abc.ABC):
                meta1: int


                @abc.abstractmethod
                def abstract_method(
                    self,
                    a: List[int],
                    b: Dict[int, bool],
                ) -> Union[str, int]:
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


def test_ClassSpec_base_classes_and_imports(LANG: SupportedLang) -> None:
    s = Script()

    c_pet = s.also(ClassSpec("Pet", docstring=["A kind of animal"]))
    c_pet.addPythonBaseClass("Animal")
    c_pet.setPHPParentClass("Animal")
    c_pet.setTypeScriptParentClass("Animal")
    c_pet.alsoImportPy("animals", ["Animal"])
    # TODO: add support for setting parent's initargs?
    c_pet.addProperty("species", str, initarg=True)

    c_dog = s.also(ClassSpec("Dog", docstring=["A dog that is a pet."]))
    c_dog.addPythonBaseClass("Pet")
    c_dog.addPythonBaseClass("Animal")
    c_dog.setPHPParentClass("Pet")
    c_dog.setTypeScriptParentClass("Pet")
    c_dog.addProperty("name", str, initarg=True)

    source_code = s.get_source_code(lang=LANG)

    if LANG == "php":
        expected = """
            <?php

            /**
             * A kind of animal
             */
            class Pet extends Animal {
                /** @var string */
                public $species;

                public function __construct(
                    string $species
                ) {
                    $this->species = $species;
                    parent::__construct();
                }
            }
            /**
             * A dog that is a pet.
             */
            class Dog extends Pet {
                /** @var string */
                public $name;

                public function __construct(
                    string $name
                ) {
                    $this->name = $name;
                    parent::__construct();
                }
            }
            """
    elif LANG == "python":
        expected = '''
            from animals import Animal

            class Pet(Animal):
                """
                A kind of animal
                """

                species: str


                def __init__(
                    self,
                    species: str,
                ) -> None:
                    self.species = species
                    super().__init__()

            class Dog(Pet, Animal):
                """
                A dog that is a pet.
                """

                name: str


                def __init__(
                    self,
                    name: str,
                ) -> None:
                    self.name = name
                    super().__init__()

            '''
    else:
        assert LANG == "typescript"
        expected = """
            /**
             * A kind of animal
             */
            class Pet extends Animal {
                public species: string;

                public constructor(
                    species: string,
                ) {
                    this.species = species;
                    super();
                }
            }
            /**
             * A dog that is a pet.
             */
            class Dog extends Pet {
                public name: string;

                public constructor(
                    name: string,
                ) {
                    this.name = name;
                    super();
                }
            }
            """

    assert source_code == dedent(expected).lstrip()


def test_ClassSpec_imports_everything(LANG: SupportedLang) -> None:
    s = Script()

    c = s.also(ClassSpec("NumberBox"))
    c.alsoImportPy("readline")
    c.alsoImportTS("math-fns", ["strict_mode"])
    # TODO: also test PHP imports

    # adding this property should force the script to import module1.Foo as
    # well as typing.List
    custom1 = CrossCustomType(python="Foo", typescript="Foo", phplang="Foo", phpdoc="Foo")
    custom1.alsoImportPy("module1", ["Foo"])
    # TODO: add tests for Typescript imports
    # TODO: add tests for PHP imports
    c.addProperty("some_prop", listof(custom1))
    p_num = c.addProperty("num", maybe(int), initarg=True)

    # create a Factory method
    factoryfn = c.createMethod(
        "random",
        CrossCustomType(
            python="NumberBox", typescript="NumberBox", phplang="NumberBox", phpdoc="NumberBox"
        ),
        isstaticmethod=True,
    )
    factoryfn.alsoReturn(
        PanCall.callClassConstructor("NumberBox", PanCall("get_random_int", pan(1), pan(10)))
    )
    factoryfn.alsoImportPy("math_fns", ["get_random_int"])
    factoryfn.alsoImportTS("math-fns", ["get_random_int"])

    # other method with body
    printnum = c.createMethod(
        "printnum",
        CrossNull(),
    )
    # this should cause import of typing.Literal
    v_wanted = printnum.addPositionalArg("wanted", lit(True, False))
    with printnum.withCond(v_wanted) as cond:
        cond.alsoImportPy("print_fns", ["print_line", "format_msg"])
        cond.alsoImportTS("print_fns", ["print_line", "format_msg"])
        # TODO: add tests for PHP imports
        cond.also(PanCall("print_line", PanCall("format_msg", p_num)))

    source_code = s.get_source_code(lang=LANG)

    if LANG == "php":
        expected = """
            <?php

            class NumberBox {
                /** @var mixed */
                public $some_prop;
                /** @var null|int */
                public $num;

                public function __construct(
                    $num
                ) {
                    $this->num = $num;
                }

                static public function random(
                ): NumberBox {
                    return new NumberBox(get_random_int(1, 10));
                }

                public function printnum(
                    bool $wanted
                ) {
                    if ($wanted) {
                        print_line(format_msg($this->num));
                    }

                }
            }
            """
    elif LANG == "python":
        expected = """
            import readline

            from math_fns import get_random_int
            from module1 import Foo
            from print_fns import format_msg, print_line
            from typing import List, Literal, Optional

            class NumberBox:
                some_prop: 'List[Foo]'
                num: Optional[int]


                def __init__(
                    self,
                    num: Optional[int],
                ) -> None:
                    self.num = num


                @classmethod
                def random(
                    class_,
                ) -> 'NumberBox':
                    return NumberBox(get_random_int(1, 10))


                def printnum(
                    self,
                    wanted: Literal[True, False],
                ) -> None:
                    if wanted:
                        print_line(format_msg(self.num))


            """
    else:
        assert LANG == "typescript"
        expected = """
            import {get_random_int} from 'math-fns';
            import {strict_mode} from 'math-fns';
            import {format_msg} from 'print_fns';
            import {print_line} from 'print_fns';

            class NumberBox {
                public some_prop: Array<Foo>;
                public num: number | null;

                public constructor(
                    num: number | null,
                ) {
                    this.num = num;
                }

                static random(
                ): NumberBox {
                    return new NumberBox(get_random_int(1, 10));
                }

                public printnum(
                    wanted: true | false,
                ): null {
                    if (wanted) {
                        print_line(format_msg(this.num));
                    }

                }
            }
            """

    assert source_code == dedent(expected).lstrip()


def test_ClassSpec_typescript_and_python_features(LANG: SupportedLang) -> None:
    s = Script()

    c = s.also(ClassSpec("Class1", tsexport=True, pydataclass=True))
    c.addProperty("locked_prop", str, tsreadonly=True)
    c.addProperty("watchable_prop", str, tsobservable=True)

    source_code = s.get_source_code(lang=LANG)

    if LANG == "php":
        expected = """
            <?php

            class Class1 {
                /** @var string */
                public $locked_prop;
                /** @var string */
                public $watchable_prop;
            }
            """
    elif LANG == "python":
        expected = """
            from dataclasses import dataclass

            @dataclass
            class Class1:
                locked_prop: str
                watchable_prop: str

            """
    else:
        assert LANG == "typescript"
        expected = """
            import {observable} from 'mobx';

            export class Class1 {
                readonly locked_prop: string;

                @observable
                public watchable_prop: string;
            }
            """

    assert source_code == dedent(expected).lstrip()
