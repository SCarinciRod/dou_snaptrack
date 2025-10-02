from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import time
import re
import unicodedata

try:
    from dou_utils.core.extraction_utils import extract_simple_links
except Exception:
    def extract_simple_links(root, item_selector: str, link_selector: Optional[str] = None, max_items: Optional[int] = None):
        return []

try:
    from dou_utils.log_utils import get_logger
except Exception:
    import logging
    def get_logger(name: str):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        return logging.getLogger(name)

logger = get_logger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _strip_accents(s: str) -> str:
    if not isinstance(s, str):
        return "" if s is None else str(s)
    nf = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nf if unicodedata.category(ch) != "Mn")


def _norm(s: str) -> str:
    # normaliza para comparação: sem acento, colapsa espaços e minúsculas
    s = _strip_accents(s or "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


@dataclass
class CascadeConfig:
    select_strategy: str = "by_index"
    n1_index: int = 0
    n2_index: int = 1
    n3_index: Optional[int] = None

    delay_after_select_ms: int = 600
    max_items_per_combo: Optional[int] = 100

    # dynamic N2
    dynamic_n2_chunk_limit: Optional[int] = None
    dynamic_reuse_cache: bool = True

    # extração
    results_root_selector: Optional[str] = None
    result_item_selector: str = "article, li, .resultado, .item"
    result_link_selector: Optional[str] = None

    # timeouts/delays
    per_combo_timeout_ms: int = 15_000
    wait_after_n1_ms: int = 500
    wait_after_n2_ms: int = 500
    select_ready_timeout_ms: int = 30_000  # aguardar select habilitar/popular

    # submit opcional
    submit_selector: Optional[str] = None
    submit_wait_ms: int = 800

    # amostragem
    sample_size: int = 3

    stop_on_error: bool = False


@dataclass
class ComboExecutionResult:
    combo: Dict[str, Any]
    status: str
    timings: Dict[str, Any]
    counts: Dict[str, int]
    itemsSample: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dynamicExpansion: Optional[Dict[str, Any]] = None


class CascadeExecutor:
    def __init__(self, frame, config: CascadeConfig):
        self.frame = frame
        self.config = config
        self._dynamic_cache: Dict[str, List[Dict[str, Any]]] = {}

    # Diagnóstico: listar opções dos selects por índice
    def list_select_options(self, indices: List[int], max_items: int = 100) -> Dict[int, List[Dict[str, str]]]:
        out: Dict[int, List[Dict[str, str]]] = {}
        for idx in indices:
            try:
                sel = self.frame.locator("select").nth(idx)
                opts = sel.locator("option")
                try:
                    n = opts.count()
                except Exception:
                    n = 0
                arr = []
                for i in range(min(n, max_items)):
                    o = opts.nth(i)
                    v = (o.get_attribute("value") or "").strip()
                    t = (o.inner_text() or "").strip()
                    dis = (o.get_attribute("disabled") is not None)
                    arr.append({"value": v, "text": t, "disabled": str(dis)})
                out[idx] = arr
            except Exception as e:
                out[idx] = [{"error": str(e)}]
        return out

    def run(self, plan: Dict[str, Any], limit: Optional[int] = None) -> Dict[str, Any]:
        combos = plan.get("combos") or []
        dynamic_n2 = bool(plan.get("dynamicN2"))
        if limit:
            combos = combos[:limit]

        results: List[Dict[str, Any]] = []
        total_ok = total_empty = total_error = 0
        start_global = time.time()

        for combo in combos:
            if self.config.stop_on_error and total_error > 0:
                logger.warning("Parando por stop_on_error após primeira falha.")
                break

            if dynamic_n2 and combo.get("_dynamicN2"):
                expansions = self._expand_n2_for_n1(combo)
                for ecombo in expansions:
                    r = self._exec_combo(ecombo)
                    results.append(asdict(r))
                    total_ok, total_empty, total_error = self._accumulate(r, total_ok, total_empty, total_error)
            else:
                r = self._exec_combo(combo)
                results.append(asdict(r))
                total_ok, total_empty, total_error = self._accumulate(r, total_ok, total_empty, total_error)

        duration = round(time.time() - start_global, 3)
        summary = {
            "totalCombosPlanned": len(plan.get("combos") or []),
            "totalExecuted": len(results),
            "ok": total_ok,
            "empty": total_empty,
            "error": total_error,
            "durationSec": duration
        }
        return {
            "schema": {"name": "cascadeResult", "version": "1.0"},
            "generatedAt": utc_now_iso(),
            "planMeta": {
                "dynamicN2": dynamic_n2,
                "originalCombos": len(plan.get("combos") or [])
            },
            "summary": summary,
            "results": results
        }

    def _accumulate(self, r: ComboExecutionResult, ok: int, empty: int, err: int) -> Tuple[int, int, int]:
        if r.status == "ok":
            ok += 1
        elif r.status == "empty":
            empty += 1
        else:
            err += 1
        return ok, empty, err

    def _expand_n2_for_n1(self, combo: Dict[str, Any]) -> List[Dict[str, Any]]:
        key1 = combo.get("key1")
        cache_key = f"n1::{key1}"
        if self.config.dynamic_reuse_cache and cache_key in self._dynamic_cache:
            opts = self._dynamic_cache[cache_key]
            logger.debug("Reutilizando cache dynamicN2 para %s (%d opções)", key1, len(opts))
        else:
            try:
                self._select_level(1, key1)
                self._delay_ms(self.config.wait_after_n1_ms)
                # Aguarda N2 habilitar e popular
                self._wait_for_select_ready(self.config.n2_index, timeout_ms=self.config.select_ready_timeout_ms)
                opts = self._extract_options_from_select(self.config.n2_index)
                # Filtrar sentinelas básicos (opção vazia/placeholder)
                opts = [o for o in opts if (o.get("value") or o.get("text")) and (o.get("text") or "").strip().lower() not in ("selecionar", "selecione")]
                if self.config.dynamic_n2_chunk_limit:
                    opts = opts[: self.config.dynamic_n2_chunk_limit]
                if self.config.dynamic_reuse_cache:
                    self._dynamic_cache[cache_key] = opts
                logger.info("Expandiu dynamicN2 para %s -> %d opções", key1, len(opts))
            except Exception:
                logger.exception("Falha expandindo dynamicN2 para key1=%s", key1)
                return []

        expansions = []
        for o2 in opts:
            expansions.append({
                "key1": key1,
                "label1": combo.get("label1"),
                "key2": o2.get("value"),
                "label2": o2.get("text"),
                "key3": combo.get("key3"),
                "label3": combo.get("label3")
            })
        return expansions

    def _exec_combo(self, combo: Dict[str, Any]) -> ComboExecutionResult:
        t0 = time.time()
        started_at = utc_now_iso()
        errors: List[str] = []
        status = "ok"
        items: List[Dict[str, Any]] = []

        try:
            key1 = combo.get("key1")
            key2 = combo.get("key2")
            key3 = combo.get("key3")

            # N1
            if key1 is not None:
                self._select_level(1, key1)
                self._delay_ms(self.config.wait_after_n1_ms)

            # Antes de N2: aguarda N2 habilitar/popular em cenários dependentes
            if key2 is not None:
                self._wait_for_select_ready(self.config.n2_index, timeout_ms=self.config.select_ready_timeout_ms)
                self._select_level(2, key2)
                self._delay_ms(self.config.wait_after_n2_ms)

            # N3 (se configurado)
            if key3 is not None and self.config.n3_index is not None:
                # Em cenários dependentes, tipo pode habilitar apenas após N2
                self._wait_for_select_ready(self.config.n3_index, timeout_ms=self.config.select_ready_timeout_ms)
                self._select_level(3, key3)

            # Submit opcional
            if self.config.submit_selector:
                try:
                    btn = self.frame.locator(self.config.submit_selector)
                    btn.click()
                    self._delay_ms(self.config.submit_wait_ms)
                except Exception as e:
                    logger.warning("Falha ao clicar submit_selector=%s: %s", self.config.submit_selector, e)

            # Extrair resultados
            items = self._extract_results()
            if not items:
                status = "empty"

        except Exception as e:
            logger.exception("Erro em combo key1=%s key2=%s", combo.get("key1"), combo.get("key2"))
            errors.append(str(e))
            status = "error"

        duration_ms = int((time.time() - t0) * 1000)
        sample = items[: self.config.sample_size]
        return ComboExecutionResult(
            combo={"key1": combo.get("key1"), "key2": combo.get("key2"), "key3": combo.get("key3")},
            status=status,
            timings={"start": started_at, "end": utc_now_iso(), "durationMs": duration_ms},
            counts={"items": len(items)},
            itemsSample=sample,
            errors=errors or []
        )

    def _wait_for_select_ready(self, index: int, timeout_ms: int = 30000):
        start = time.time()
        sel = self.frame.locator("select").nth(index)
        last_count = -1
        while True:
            try:
                enabled = sel.is_enabled()
                opts = sel.locator("option")
                count = opts.count()
                # Considera "pronto" quando está enabled e há mais de 1 opção (ignora placeholder)
                if enabled and count > 1:
                    return
                last_count = count
            except Exception:
                pass
            if (time.time() - start) * 1000 > timeout_ms:
                raise TimeoutError(f"Timeout aguardando select idx={index} habilitar e popular (última contagem={last_count}).")
            time.sleep(0.2)

    def _select_level(self, level: int, value: Any):
        if self.config.select_strategy != "by_index":
            raise NotImplementedError("Apenas select_strategy=by_index implementado.")
        index_map = {1: self.config.n1_index, 2: self.config.n2_index, 3: self.config.n3_index}
        sel_index = index_map.get(level)
        if sel_index is None:
            raise RuntimeError(f"Índice não definido para nível {level}.")

        locator = self.frame.locator("select").nth(sel_index)

        # Aguarda select pronto sempre que possível
        try:
            self._wait_for_select_ready(sel_index, timeout_ms=self.config.select_ready_timeout_ms)
        except Exception:
            # segue mesmo assim; select_option fará seu próprio wait
            pass

        # 1) Tenta direto por value
        try:
            locator.select_option(str(value))
            logger.debug("Selecionado nível %s por value='%s' (índice %s).", level, value, sel_index)
            return
        except Exception:
            pass

        # 2) Fallback: varrer options com matching por value ou label (com normalização)
        options = locator.locator("option")
        try:
            n = options.count()
        except Exception:
            n = 0

        target_idx = None
        value_s = str(value or "")
        value_norm = _norm(value_s)

        samples = []
        for i in range(n):
            opt = options.nth(i)
            v = (opt.get_attribute("value") or "").strip()
            t = (opt.inner_text() or "").strip()
            if i < 5:
                disabled = (opt.get_attribute("disabled") is not None)
                samples.append({"i": i, "value": v, "text": t, "disabled": str(disabled)})

            # matches diretos
            if value_s == v or value_s == t:
                target_idx = i
                break
            # matches normalizados (acento/case/espacos)
            if value_norm and (value_norm == _norm(v) or value_norm == _norm(t)):
                target_idx = i
                break

        if target_idx is None:
            logger.error("Valor '%s' não encontrado no select nível %s (índice %s). Amostras: %s", value_s, level, sel_index, samples)
            raise RuntimeError(f"Valor '{value_s}' não encontrado no select nível {level}.")

        opt_val = (options.nth(target_idx).get_attribute("value") or "").strip()
        locator.select_option(opt_val)
        logger.debug("Selecionado nível %s por fallback (idx=%s, value='%s').", level, target_idx, opt_val)

    def _extract_options_from_select(self, index: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        locator = self.frame.locator("select").nth(index)
        options = locator.locator("option")
        try:
            count = options.count()
        except Exception:
            count = 0
        for i in range(count):
            opt = options.nth(i)
            v = (opt.get_attribute("value") or "").strip()
            t = (opt.inner_text() or "").strip()
            if not v and not t:
                continue
            out.append({"value": v, "text": t})
        return out

    def _extract_results(self) -> List[Dict[str, Any]]:
        root = self.frame
        if self.config.results_root_selector:
            root = self.frame.locator(self.config.results_root_selector)
        return extract_simple_links(
            root,
            item_selector=self.config.result_item_selector,
            link_selector=self.config.result_link_selector,
            max_items=self.config.max_items_per_combo
        )

    def _delay_ms(self, ms: int):
        if ms and ms > 0:
            time.sleep(ms / 1000.0)
