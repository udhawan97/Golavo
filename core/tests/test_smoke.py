from golavo_core import __version__


def test_version_is_string() -> None:
    assert isinstance(__version__, str)
    assert __version__.count(".") >= 2
