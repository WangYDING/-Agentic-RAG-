from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from src.presentation import configure_utf8_output


def installed_web_app_path() -> Path:
    spec = importlib.util.find_spec("app")
    if spec is None or spec.origin is None:
        raise RuntimeError("安装包中缺少 Web 入口模块 app.py。")
    return Path(spec.origin)


def main() -> int:
    configure_utf8_output()
    from streamlit.web import cli as streamlit_cli

    sys.argv = [
        "streamlit",
        "run",
        str(installed_web_app_path()),
        *sys.argv[1:],
    ]
    return streamlit_cli.main()
