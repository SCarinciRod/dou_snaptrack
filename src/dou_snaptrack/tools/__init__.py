"""
Ferramentas internas de diagnóstico e análise do DOU SnapTrack.

Uso como módulo:
    from dou_snaptrack.tools import run_dou_diagnostic

Uso como CLI:
    python -m dou_snaptrack.tools.fetch_diagnostics --target dou
"""

# Lazy imports to avoid circular import warnings when running as __main__
def __getattr__(name):
    if name == "DiagnosticResult":
        from .fetch_diagnostics import DiagnosticResult
        return DiagnosticResult
    elif name == "run_dou_diagnostic":
        from .fetch_diagnostics import run_dou_diagnostic
        return run_dou_diagnostic
    elif name == "run_eagendas_diagnostic":
        from .fetch_diagnostics import run_eagendas_diagnostic
        return run_eagendas_diagnostic
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "DiagnosticResult",
    "run_dou_diagnostic",
    "run_eagendas_diagnostic",
]
