"""
Widget de diagnóstico de performance para Streamlit UI.

Pode ser integrado na interface para mostrar métricas de performance
em tempo real durante operações de fetch.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any

import streamlit as st


@dataclass
class UITimingEntry:
    """Entrada de timing para exibição na UI."""
    name: str
    elapsed: float
    success: bool = True
    
    @property
    def elapsed_ms(self) -> float:
        return self.elapsed * 1000
    
    @property
    def color(self) -> str:
        if not self.success:
            return "🔴"
        if self.elapsed > 5:
            return "🟡"
        if self.elapsed > 2:
            return "🟢"
        return "⚡"


@dataclass 
class UIPerformanceTracker:
    """Rastreador de performance para exibição na UI."""
    operation: str
    timings: list[UITimingEntry] = field(default_factory=list)
    _start: float = 0
    _current: str | None = None
    _current_start: float = 0
    
    def start(self) -> None:
        """Inicia tracking total."""
        self._start = time.perf_counter()
    
    def begin_step(self, name: str) -> None:
        """Inicia uma etapa."""
        self._current = name
        self._current_start = time.perf_counter()
    
    def end_step(self, success: bool = True) -> float:
        """Finaliza etapa atual."""
        if not self._current:
            return 0
        elapsed = time.perf_counter() - self._current_start
        self.timings.append(UITimingEntry(
            name=self._current,
            elapsed=elapsed,
            success=success
        ))
        self._current = None
        return elapsed
    
    @property
    def total_elapsed(self) -> float:
        return time.perf_counter() - self._start if self._start else 0
    
    def render_summary(self) -> None:
        """Renderiza resumo de performance no Streamlit."""
        if not self.timings:
            return
        
        total = self.total_elapsed
        
        st.markdown(f"**📊 Performance: {self.operation}** ({total:.1f}s total)")
        
        cols = st.columns(min(len(self.timings), 4))
        for i, entry in enumerate(self.timings):
            col_idx = i % 4
            with cols[col_idx]:
                pct = (entry.elapsed / total * 100) if total > 0 else 0
                st.metric(
                    label=f"{entry.color} {entry.name}",
                    value=f"{entry.elapsed:.1f}s",
                    delta=f"{pct:.0f}%"
                )
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "total": self.total_elapsed,
            "timings": [
                {"name": t.name, "elapsed": t.elapsed, "success": t.success}
                for t in self.timings
            ]
        }


def render_performance_expander(tracker: UIPerformanceTracker) -> None:
    """Renderiza os detalhes de performance em um expander."""
    with st.expander("📈 Detalhes de Performance", expanded=False):
        tracker.render_summary()
        
        # Tabela detalhada
        if tracker.timings:
            st.markdown("---")
            st.markdown("**Breakdown detalhado:**")
            
            total = tracker.total_elapsed
            for entry in sorted(tracker.timings, key=lambda x: x.elapsed, reverse=True):
                pct = (entry.elapsed / total * 100) if total > 0 else 0
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                status = "✓" if entry.success else "✗"
                st.code(f"[{status}] {entry.name:20s} {entry.elapsed:6.2f}s  {bar} {pct:5.1f}%")


# Função helper para parse de timing de stderr
def parse_subprocess_timing(stderr: str) -> dict[str, float]:
    """Parse timings do formato [SUBPROCESS TIMING]."""
    import re
    
    timings = {}
    patterns = [
        r'\[SUBPROCESS TIMING(?: L\d)?\]\s*(\w+):\s*([\d.]+)s',
        r'\[TIMING\]\s*([^:]+):\s*([\d.]+)s',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, stderr):
            name = match.group(1).strip()
            time_val = float(match.group(2))
            timings[name] = time_val
    
    return timings


def show_timing_from_stderr(stderr: str, operation: str = "Fetch") -> None:
    """Mostra timing extraído de stderr no Streamlit."""
    timings = parse_subprocess_timing(stderr)
    
    if not timings:
        return
    
    tracker = UIPerformanceTracker(operation=operation)
    for name, elapsed in timings.items():
        tracker.timings.append(UITimingEntry(name=name, elapsed=elapsed))
    
    render_performance_expander(tracker)
