"""
Ferramentas de análise de performance interna para DOU SnapTrack.

Este módulo fornece utilitários para medir e diagnosticar
performance de operações de fetch e coleta de dados.

Uso:
    from dou_snaptrack.utils.perf_analyzer import TimingContext, PerformanceReport

    with TimingContext("operação") as t:
        # código a medir
        pass
    print(t.elapsed)
"""
from __future__ import annotations

import functools
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

logger = logging.getLogger("dou_snaptrack.utils.perf_analyzer")

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class TimingResult:
    """Resultado de uma medição de tempo."""
    name: str
    elapsed: float
    success: bool = True
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed * 1000

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"[{status}] {self.name}: {self.elapsed:.2f}s"


class TimingContext:
    """Context manager para medir tempo de execução."""

    def __init__(self, name: str, log_to_stderr: bool = True):
        self.name = name
        self.log_to_stderr = log_to_stderr
        self._start: float = 0
        self._elapsed: float = 0
        self._success: bool = True
        self._error: str | None = None

    def __enter__(self) -> TimingContext:
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._elapsed = time.perf_counter() - self._start
        if exc_type is not None:
            self._success = False
            self._error = f"{exc_type.__name__}: {exc_val}"

        if self.log_to_stderr:
            status = "✓" if self._success else "✗"
            print(f"[PERF {status}] {self.name}: {self._elapsed:.2f}s", file=sys.stderr, flush=True)

        return False  # Não suprimir exceções

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed * 1000

    def result(self) -> TimingResult:
        return TimingResult(
            name=self.name,
            elapsed=self._elapsed,
            success=self._success,
            error=self._error
        )


class PerformanceReport:
    """Coletor de métricas de performance."""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.timings: list[TimingResult] = []
        self._start_time: float = 0
        self._total_elapsed: float = 0

    def start(self) -> None:
        """Inicia a contagem total."""
        self._start_time = time.perf_counter()

    def stop(self) -> None:
        """Para a contagem total."""
        if self._start_time > 0:
            self._total_elapsed = time.perf_counter() - self._start_time

    def add_timing(self, result: TimingResult) -> None:
        """Adiciona um resultado de timing."""
        self.timings.append(result)

    def time(self, name: str) -> TimingContext:
        """Cria um context manager que adiciona o resultado automaticamente."""
        ctx = TimingContext(name, log_to_stderr=True)
        # Hook para adicionar ao report depois
        original_exit = ctx.__exit__

        def patched_exit(exc_type, exc_val, exc_tb):
            result = original_exit(exc_type, exc_val, exc_tb)
            self.add_timing(ctx.result())
            return result

        ctx.__exit__ = patched_exit
        return ctx

    @property
    def total_elapsed(self) -> float:
        return self._total_elapsed or sum(t.elapsed for t in self.timings)

    def report(self, to_stderr: bool = True) -> str:
        """Gera relatório de performance."""
        lines = [
            "",
            "=" * 60,
            f"📊 PERFORMANCE REPORT: {self.operation_name}",
            "=" * 60,
        ]

        for t in self.timings:
            status = "✓" if t.success else "✗"
            lines.append(f"  [{status}] {t.name}: {t.elapsed:.2f}s ({t.elapsed_ms:.0f}ms)")
            if t.error:
                lines.append(f"      Error: {t.error}")

        lines.append("-" * 60)
        lines.append(f"  TOTAL: {self.total_elapsed:.2f}s")
        lines.append("=" * 60)

        report_text = "\n".join(lines)

        if to_stderr:
            print(report_text, file=sys.stderr, flush=True)

        return report_text

    def to_dict(self) -> dict[str, Any]:
        """Exporta como dicionário."""
        return {
            "operation": self.operation_name,
            "total_elapsed": self.total_elapsed,
            "timings": [
                {
                    "name": t.name,
                    "elapsed": t.elapsed,
                    "elapsed_ms": t.elapsed_ms,
                    "success": t.success,
                    "error": t.error,
                }
                for t in self.timings
            ]
        }


def timed(name: str | None = None, log: bool = True) -> Callable[[F], F]:
    """Decorator para medir tempo de execução de funções."""
    def decorator(func: F) -> F:
        op_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                if log:
                    print(f"[PERF ✓] {op_name}: {elapsed:.2f}s", file=sys.stderr, flush=True)
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                if log:
                    print(f"[PERF ✗] {op_name}: {elapsed:.2f}s ({type(e).__name__})", file=sys.stderr, flush=True)
                raise

        return wrapper  # type: ignore
    return decorator
