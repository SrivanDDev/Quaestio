from pathlib import Path

import pytest


@pytest.fixture
def sample_log():
    return Path(__file__).resolve().parents[1] / "examples" / "sample.log"
