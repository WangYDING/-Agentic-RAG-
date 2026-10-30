import pytest

from src import index_cli


def test_index_cli_help_lists_build_rebuild_and_check(capsys):
    with pytest.raises(SystemExit) as error:
        index_cli.main(["--help"])

    assert error.value.code == 0
    output = capsys.readouterr().out
    assert "build" in output
    assert "rebuild" in output
    assert "check" in output
