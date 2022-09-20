from typing import Any, Iterable

import pytest
from _paradoxtest import SupportedLang


@pytest.fixture(params=['python', 'php', 'typescript'])
def LANG(request: Any) -> Iterable[SupportedLang]:
    yield request.param
