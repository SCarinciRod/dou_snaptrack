from __future__ import annotations

import contextlib
import os
import pathlib
import platform
import subprocess
import sys
import webbrowser

# Launcher para `python -m dou_snaptrack.ui.launch` ou entry point `dou-ui`.
# Em Windows, delega ao launcher gerenciado (PowerShell) que abre o navegador com loader e faz auto-kill.
# Fora do Windows (ou sem o PS1), cai para `streamlit run` e tenta abrir o navegador.


def main():  # pragma: no cover
    here = pathlib.Path(__file__).resolve()
    app_path = here.with_name("app.py")
    if not app_path.exists():
        print("[ERRO] app.py não encontrado em", app_path)
        sys.exit(1)
    # Política de lançamento:
    # Por padrão em ambiente de desenvolvimento (IDE), evitar launcher gerenciado para não criar processos
    # extras que confundem o Simple Browser. Ativar somente se variável explícita definida.
    use_managed = bool(os.environ.get("DOU_USE_MANAGED_UI"))
    if platform.system().lower().startswith("win") and use_managed:
        repo_root = here.parents[3]  # .../src/dou_snaptrack/ui/launch.py -> repo root
        ps1 = repo_root / "scripts" / "run-ui-managed.ps1"
        if ps1.exists():
            port = os.environ.get("DOU_UI_PORT", "8501")
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
                str(ps1),
                "-Port",
                port,
            ]
            print("[INFO] Iniciando UI via launcher gerenciado (variável DOU_USE_MANAGED_UI=1):", " ".join(cmd))
            try:
                subprocess.Popen(cmd, cwd=str(repo_root))
                return 0
            except Exception as e:
                print("[WARN] Falha ao iniciar gerenciador, usando fallback direto:", e)

    # Fallback: streamlit direto. Não usar headless para permitir abrir navegador.
    port_direct = os.environ.get("DOU_UI_PORT", "8501")
    extra_flags = [
        "--browser.gatherUsageStats=false",
        "--server.headless=true",  # headless evita interações de abertura automática em alguns ambientes
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        f"--server.port={port_direct}",
    ]
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), *extra_flags]
    print("[INFO] Iniciando UI diretamente (modo IDE):", " ".join(cmd))
    with contextlib.suppress(Exception):
        webbrowser.open(f"http://localhost:{port_direct}", new=2)
    return subprocess.call(cmd)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
