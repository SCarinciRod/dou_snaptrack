from __future__ import annotations

import contextlib
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

    # Tentar caminho preferencial no Windows: scripts\run-ui-managed.ps1
    if platform.system().lower().startswith("win"):
        repo_root = here.parents[3]  # .../src/dou_snaptrack/ui/launch.py -> repo root
        ps1 = repo_root / "scripts" / "run-ui-managed.ps1"
        if ps1.exists():
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
                "8501",
            ]
            print("[INFO] Iniciando UI via launcher gerenciado:", " ".join(cmd))
            # Não bloquear: iniciar e sair
            try:
                subprocess.Popen(cmd, cwd=str(repo_root))
                return 0
            except Exception as e:
                print("[WARN] Falha ao iniciar gerenciador:", e)
                # fallback abaixo

    # Fallback: streamlit direto. Não usar headless para permitir abrir navegador.
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), "--browser.gatherUsageStats=false"]
    print("[INFO] Iniciando UI diretamente:", " ".join(cmd))
    with contextlib.suppress(Exception):
        # Tenta abrir o navegador para a URL padrão; Streamlit pode não abrir automaticamente em alguns casos.
        webbrowser.open("http://localhost:8501", new=2)
    return subprocess.call(cmd)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
