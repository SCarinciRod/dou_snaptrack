"""
Ferramenta de diagnóstico de performance para DOU e E-Agendas.

Analisa tempos de fetch, identifica gargalos e sugere otimizações.

Uso via linha de comando:
    python -m dou_snaptrack.tools.fetch_diagnostics --target dou
    python -m dou_snaptrack.tools.fetch_diagnostics --target eagendas
    python -m dou_snaptrack.tools.fetch_diagnostics --all
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DiagnosticResult:
    """Resultado de diagnóstico de uma operação."""
    target: str
    operation: str
    elapsed_seconds: float
    breakdown: dict[str, float]
    raw_stderr: str
    success: bool
    error: str | None = None
    recommendations: list[str] | None = None

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed_seconds * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "operation": self.operation,
            "elapsed_seconds": self.elapsed_seconds,
            "elapsed_ms": self.elapsed_ms,
            "breakdown": self.breakdown,
            "success": self.success,
            "error": self.error,
            "recommendations": self.recommendations or [],
        }


def parse_timing_output(stderr: str) -> dict[str, float]:
    """Extrai tempos do output stderr."""
    timings = {}

    patterns = [
        r'\[SUBPROCESS TIMING(?: L\d)?\]\s*(\w+):\s*([\d.]+)s',
        r'\[PERF [✓✗]\]\s*([^:]+):\s*([\d.]+)s',
        r'\[TIMING\]\s*([^:]+):\s*([\d.]+)s',
        r'(\w+)_elapsed:\s*([\d.]+)',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, stderr):
            name = match.group(1).strip()
            time_val = float(match.group(2))
            timings[name] = time_val

    return timings


def run_dou_diagnostic() -> DiagnosticResult:
    """Executa diagnóstico de fetch do DOU."""
    print("[DOU] Iniciando diagnóstico de fetch N1...", file=sys.stderr)

    script = '''
import sys
import time

# Instrumentação de timing
class TimingLogger:
    def __init__(self):
        self.timings = {}
        self.start_time = None

    def start(self, name):
        self.start_time = time.perf_counter()
        self.current = name

    def stop(self):
        if self.start_time:
            elapsed = time.perf_counter() - self.start_time
            self.timings[self.current] = elapsed
            print(f"[TIMING] {self.current}: {elapsed:.2f}s", file=sys.stderr, flush=True)
            self.start_time = None

timer = TimingLogger()

# Fase 1: Import
timer.start("import")
try:
    from dou_snaptrack.ui.pages.dou_fetch import find_system_browser_exe
    from dou_snaptrack.utils.browser import build_dou_url
    timer.stop()
except Exception as e:
    timer.stop()
    print(f"[ERROR] Import failed: {e}", file=sys.stderr)
    sys.exit(1)

# Fase 2: Browser discovery
timer.start("browser_discovery")
exe_path = find_system_browser_exe()
timer.stop()
print(f"[INFO] Browser: {exe_path}", file=sys.stderr)

# Fase 3: Playwright launch
timer.start("playwright_launch")
try:
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    timer.stop()
except Exception as e:
    timer.stop()
    print(f"[ERROR] Playwright start failed: {e}", file=sys.stderr)
    sys.exit(1)

# Fase 4: Browser start
timer.start("browser_start")
try:
    browser = pw.chromium.launch(
        channel="chrome",
        headless=True,
        args=["--disable-gpu", "--no-sandbox"]
    )
    timer.stop()
except:
    timer.start("browser_start_fallback")
    browser = pw.chromium.launch(
        executable_path=exe_path,
        headless=True,
        args=["--disable-gpu", "--no-sandbox"]
    )
    timer.stop()

# Fase 5: Page navigation
timer.start("navigation")
page = browser.new_page()
url = build_dou_url("DO1", None)
page.goto(url, wait_until="domcontentloaded")
timer.stop()

# Fase 6: Wait for content (otimizado com wait_for_function)
timer.start("wait_content")
try:
    page.wait_for_function(
        "() => document.querySelector('select') !== null || document.querySelector('.selectize-input') !== null",
        timeout=3000
    )
    timer.stop()
except:
    timer.stop()
    print("[WARN] Wait function timeout", file=sys.stderr)

# Fase 7: Extract data (simulated)
timer.start("extract")
try:
    content_len = len(page.content())
    timer.stop()
    print(f"[INFO] Page content: {content_len} chars", file=sys.stderr)
except Exception as e:
    timer.stop()
    print(f"[WARN] Extract: {e}", file=sys.stderr)

# Cleanup
timer.start("cleanup")
browser.close()
pw.stop()
timer.stop()

# Report total
total = sum(timer.timings.values())
print(f"[TIMING] total: {total:.2f}s", file=sys.stderr)
print("SUCCESS")
'''

    start = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parent.parent.parent.parent),
        )
        elapsed = time.perf_counter() - start

        stderr = result.stderr
        stdout = result.stdout
        success = "SUCCESS" in stdout

        breakdown = parse_timing_output(stderr)

        recommendations = []
        if breakdown.get("browser_start", 0) > 2:
            recommendations.append("Browser start lento - verificar se Chrome está instalado")
        if breakdown.get("navigation", 0) > 3:
            recommendations.append("Navegação lenta - verificar conexão ou usar cache")
        if breakdown.get("wait_content", 0) > 3:
            recommendations.append("Wait content lento - considerar wait_for_function em vez de wait_for_selector")

        return DiagnosticResult(
            target="dou",
            operation="fetch_n1",
            elapsed_seconds=elapsed,
            breakdown=breakdown,
            raw_stderr=stderr,
            success=success,
            error=None if success else "Fetch failed",
            recommendations=recommendations,
        )

    except subprocess.TimeoutExpired:
        return DiagnosticResult(
            target="dou",
            operation="fetch_n1",
            elapsed_seconds=60,
            breakdown={},
            raw_stderr="",
            success=False,
            error="Timeout (60s)",
            recommendations=["Verificar conectividade", "Verificar se browser está acessível"],
        )
    except Exception as e:
        return DiagnosticResult(
            target="dou",
            operation="fetch_n1",
            elapsed_seconds=0,
            breakdown={},
            raw_stderr="",
            success=False,
            error=str(e),
        )


def run_eagendas_diagnostic() -> DiagnosticResult:
    """Executa diagnóstico de fetch do E-Agendas."""
    print("[E-AGENDAS] Iniciando diagnóstico de fetch...", file=sys.stderr)

    script = '''
import sys
import time

class TimingLogger:
    def __init__(self):
        self.timings = {}
        self.start_time = None
        self.current = None

    def start(self, name):
        self.start_time = time.perf_counter()
        self.current = name

    def stop(self):
        if self.start_time and self.current:
            elapsed = time.perf_counter() - self.start_time
            self.timings[self.current] = elapsed
            print(f"[TIMING] {self.current}: {elapsed:.2f}s", file=sys.stderr, flush=True)
            self.start_time = None

timer = TimingLogger()

# Fase 1: Import
timer.start("import")
try:
    from dou_snaptrack.ui.pages.dou_fetch import find_system_browser_exe
    timer.stop()
except Exception as e:
    timer.stop()
    print(f"[ERROR] Import: {e}", file=sys.stderr)
    sys.exit(1)

# Fase 2: Browser discovery
timer.start("browser_discovery")
exe_path = find_system_browser_exe()
timer.stop()
print(f"[INFO] Browser: {exe_path}", file=sys.stderr)

# Fase 3: Playwright launch
timer.start("playwright_launch")
try:
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    timer.stop()
except Exception as e:
    timer.stop()
    print(f"[ERROR] Playwright: {e}", file=sys.stderr)
    sys.exit(1)

# Fase 4: Browser start
timer.start("browser_start")
try:
    browser = pw.chromium.launch(channel="chrome", headless=True, args=["--disable-gpu", "--no-sandbox"])
    timer.stop()
except:
    timer.start("browser_start_fallback")
    browser = pw.chromium.launch(executable_path=exe_path, headless=True, args=["--disable-gpu", "--no-sandbox"])
    timer.stop()

# Fase 5: Navigate to E-Agendas
timer.start("navigation")
page = browser.new_page()
page.goto("https://eagendas.cgu.gov.br/", wait_until="domcontentloaded")
timer.stop()

# Fase 6: Wait for Angular/Selectize
timer.start("wait_angular")
try:
    page.wait_for_function(
        "() => typeof angular !== 'undefined' && angular.element(document.body).injector()",
        timeout=5000
    )
    timer.stop()
except:
    timer.stop()
    print("[WARN] Angular not detected", file=sys.stderr)

timer.start("wait_selectize")
try:
    page.wait_for_function(
        "() => { const el = document.getElementById('filtro_orgao_entidade'); return !!(el && el.selectize && Object.keys(el.selectize.options||{}).length > 5); }",
        timeout=8000
    )
    timer.stop()
except:
    timer.stop()
    print("[WARN] Selectize not ready", file=sys.stderr)

# Fase 7: Extract dropdown options
timer.start("extract_options")
try:
    options = page.evaluate("""
        () => {
            const el = document.getElementById('filtro_orgao_entidade');
            if (!el || !el.selectize) return [];
            const s = el.selectize;
            const out = [];
            const opts = s.options || {};
            for (const [val, raw] of Object.entries(opts)) {
                const v = String(val ?? '');
                const t = (raw && (raw.text || raw.label || raw.nome || raw.name)) || v;
                if (!t) continue;
                if (String(t).toLowerCase().includes('selecione')) continue;
                out.push({ value: v, text: String(t) });
                if (out.length >= 5) break;
            }
            return out;
        }
    """)
    timer.stop()
    print(f"[INFO] Options found: {len(options)}", file=sys.stderr)
except Exception as e:
    timer.stop()
    print(f"[WARN] Extract: {e}", file=sys.stderr)

# Cleanup
timer.start("cleanup")
browser.close()
pw.stop()
timer.stop()

# Total
total = sum(timer.timings.values())
print(f"[TIMING] total: {total:.2f}s", file=sys.stderr)
print("SUCCESS")
'''

    start = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parent.parent.parent.parent),
        )
        elapsed = time.perf_counter() - start

        stderr = result.stderr
        stdout = result.stdout
        success = "SUCCESS" in stdout

        breakdown = parse_timing_output(stderr)

        recommendations = []
        if breakdown.get("wait_angular", 0) > 3:
            recommendations.append("Angular load lento - site pode estar sobrecarregado")
        if breakdown.get("wait_selectize", 0) > 5:
            recommendations.append("Selectize lento - considerar reduzir timeout se dados já carregados")
        if breakdown.get("navigation", 0) > 3:
            recommendations.append("Navegação lenta - verificar conectividade")

        return DiagnosticResult(
            target="eagendas",
            operation="fetch_options",
            elapsed_seconds=elapsed,
            breakdown=breakdown,
            raw_stderr=stderr,
            success=success,
            error=None if success else "Fetch failed",
            recommendations=recommendations,
        )

    except subprocess.TimeoutExpired:
        return DiagnosticResult(
            target="eagendas",
            operation="fetch_options",
            elapsed_seconds=60,
            breakdown={},
            raw_stderr="",
            success=False,
            error="Timeout (60s)",
            recommendations=["Site E-Agendas pode estar offline"],
        )
    except Exception as e:
        return DiagnosticResult(
            target="eagendas",
            operation="fetch_options",
            elapsed_seconds=0,
            breakdown={},
            raw_stderr="",
            success=False,
            error=str(e),
        )


def print_diagnostic_report(result: DiagnosticResult) -> None:
    """Imprime relatório formatado."""
    print()
    print("=" * 70)
    print(f"📊 DIAGNÓSTICO: {result.target.upper()} - {result.operation}")
    print("=" * 70)

    status = "✓ SUCESSO" if result.success else "✗ FALHA"
    print(f"Status: {status}")
    print(f"Tempo total: {result.elapsed_seconds:.2f}s ({result.elapsed_ms:.0f}ms)")

    if result.error:
        print(f"Erro: {result.error}")

    if result.breakdown:
        print()
        print("Breakdown de tempo:")
        print("-" * 40)

        sorted_times = sorted(result.breakdown.items(), key=lambda x: x[1], reverse=True)
        for name, elapsed in sorted_times:
            pct = (elapsed / result.elapsed_seconds * 100) if result.elapsed_seconds > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(f"  {name:20s} {elapsed:6.2f}s  {bar} {pct:5.1f}%")

    if result.recommendations:
        print()
        print("💡 Recomendações:")
        for rec in result.recommendations:
            print(f"  • {rec}")

    print("=" * 70)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Diagnóstico de performance de fetch DOU/E-Agendas"
    )
    parser.add_argument(
        "--target",
        choices=["dou", "eagendas", "all"],
        default="all",
        help="Target para diagnóstico (default: all)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output em formato JSON"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Número de iterações para média (default: 1)"
    )

    args = parser.parse_args()

    results = []

    if args.target in ("dou", "all"):
        for i in range(args.iterations):
            if args.iterations > 1:
                print(f"\n[DOU] Iteração {i+1}/{args.iterations}", file=sys.stderr)
            result = run_dou_diagnostic()
            results.append(result)
            if not args.json:
                print_diagnostic_report(result)

    if args.target in ("eagendas", "all"):
        for i in range(args.iterations):
            if args.iterations > 1:
                print(f"\n[E-AGENDAS] Iteração {i+1}/{args.iterations}", file=sys.stderr)
            result = run_eagendas_diagnostic()
            results.append(result)
            if not args.json:
                print_diagnostic_report(result)

    if args.json:
        output = {
            "diagnostics": [r.to_dict() for r in results],
            "summary": {
                "total_tests": len(results),
                "successful": sum(1 for r in results if r.success),
                "avg_time": sum(r.elapsed_seconds for r in results) / len(results) if results else 0,
            }
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

    return 0 if all(r.success for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
