from __future__ import annotations
import runpy
import sys
import pathlib

# Launcher simples para permitir: `python -m dou_snaptrack.ui.launch` ou entry point `dou-ui`
# Ele apenas delega para `streamlit run app.py`

def main():  # pragma: no cover
    app_path = pathlib.Path(__file__).with_name("app.py")
    if not app_path.exists():
        print("[ERRO] app.py não encontrado em", app_path)
        sys.exit(1)
    # Preferir invocar streamlit via módulo (mais portátil)
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.headless=true"]
    print("[INFO] Iniciando UI:", " ".join(cmd))
    import subprocess
    raise SystemExit(subprocess.call(cmd))

if __name__ == "__main__":  # pragma: no cover
    main()
