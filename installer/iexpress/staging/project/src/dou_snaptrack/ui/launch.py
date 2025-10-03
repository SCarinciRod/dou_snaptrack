from __future__ import annotations
import sys
import pathlib
import platform
import subprocess
import webbrowser

# Launcher para permitir: `python -m dou_snaptrack.ui.launch`.
# Em Windows, tenta chamar o launcher gerenciado do repositório, se disponível; senão cai para streamlit direto.


def main():  # pragma: no cover
    here = pathlib.Path(__file__).resolve()
    app_path = here.with_name("app.py")
    if not app_path.exists():
        print("[ERRO] app.py não encontrado em", app_path)
        sys.exit(1)

    if platform.system().lower().startswith("win"):
        # Tentar achar repo root assumindo que o instalador está em C:\Projetos\installer\... e o repo em C:\Projetos
        # Sobe diretórios até encontrar uma pasta 'scripts' com run-ui-managed.ps1
        cur = here
        repo_root = None
        for _ in range(6):
            cur = cur.parent
            if (cur / "scripts" / "run-ui-managed.ps1").exists():
                repo_root = cur
                break
        if repo_root:
            ps1 = repo_root / "scripts" / "run-ui-managed.ps1"
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
            try:
                subprocess.Popen(cmd, cwd=str(repo_root))
                return 0
            except Exception as e:
                print("[WARN] Falha ao iniciar gerenciador:", e)

    # Fallback: streamlit direto (tenta abrir navegador)
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), "--browser.gatherUsageStats=false"]
    print("[INFO] Iniciando UI diretamente:", " ".join(cmd))
    try:
        webbrowser.open("http://localhost:8501", new=2)
    except Exception:
        pass
    return subprocess.call(cmd)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
