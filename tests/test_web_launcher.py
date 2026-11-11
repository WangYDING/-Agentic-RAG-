from pathlib import Path

from src.web_launcher import installed_web_app_path


def test_web_launcher_resolves_packaged_app_module():
    path = installed_web_app_path()

    assert isinstance(path, Path)
    assert path.name == "app.py"
    assert path.is_file()
