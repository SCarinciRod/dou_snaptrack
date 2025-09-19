#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
00_map_unificado.py (Refatorado c/ suporte à nova interface do DropdownMapperService)

Compatível com:
 - Versão nova: map_all(MapAllConfig), map_pairs(MapPairsConfig, PairFilters)
 - Versão antiga (fallback): map_all(open_combos=...), map_pairs(... parâmetros soltos)

Features:
 - Descoberta unificada de dropdowns
 - Mapeamento de pares
 - Escrita atômica
 - Desambiguação de labels (--verbose-labels, --auto-disambiguate)
 - Snapshot opcional
 - Logging estruturado + traceback em caso de falha
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import inspect

# ----------------- Logging / Util -----------------
try:
    from dou_utils.log_utils import get_logger
except ImportError:  # fallback mínimo
    import logging
    def get_logger(name: str):
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        return logging.getLogger(name)

logger = get_logger(__name__)

# ----------------- Schema / constants -----------------
try:
    from dou_utils.constants import schema_block, SOURCES, utc_now_iso
except ImportError:
    def schema_block(name: str) -> Dict[str, str]:
        return {"name": name, "version": "1.0"}
    SOURCES = {"mapping": "mapping-tool"}
    def utc_now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

# ----------------- Core discovery presence check -----------------
try:
    from dou_utils.core.dropdown_discovery import discover_dropdown_roots  # noqa
except ImportError:
    discover_dropdown_roots = None

# ----------------- Mapper Service (nova e antiga interface) -----------------
NEW_INTERFACE = False
try:
    # Nova versão (refatorada)
    from dou_utils.services.dropdown_mapper_service import (
        DropdownMapperService,
        MapAllConfig,
        MapPairsConfig,
        PairFilters
    )
    NEW_INTERFACE = True
except ImportError:
    # Versão antiga (sem dataclasses)
    try:
        from dou_utils.services.dropdown_mapper_service import DropdownMapperService  # type: ignore
    except ImportError:
        DropdownMapperService = None  # será verificado em runtime
    MapAllConfig = None
    MapPairsConfig = None
    PairFilters = None
    NEW_INTERFACE = False

# ----------------- Navegação -----------------
try:
    from dou_utils.page_utils import goto, close_cookies
except ImportError:
    def goto(page, url):
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_load_state("networkidle")
    def close_cookies(page):
        pass


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def normalize_out_path(raw: str) -> Path:
    p = Path(raw)
    if os.name == "nt":
        if str(p).startswith(("/tmp", "\\tmp")) and not p.parent.exists():
            tmpdir = Path(tempfile.gettempdir())
            p = tmpdir / p.name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def atomic_write_json(path: Path, data: Dict[str, Any]):
    import json as _json
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp_map_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


def snapshot_html(page, target_dir: Path, prefix: str = "snapshot"):
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        html = page.content()
        ts = datetime.now(timezone.utc).strftime("%H%M%S")
        out = target_dir / f"{prefix}_{ts}.html"
        out.write_text(html, encoding="utf-8")
        logger.info("Snapshot salvo", extra={"file": str(out)})
    except Exception as e:
        logger.warning("Falha ao salvar snapshot", extra={"err": str(e)})


def build_url(data: str, secao: str) -> str:
    return f"https://www.in.gov.br/leiturajornal?data={data}&secao={secao}"


def create_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Mapeia dropdowns e pares N1->N2 da página do DOU."
    )
    p.add_argument("--dou", action="store_true", help="Mantido por compatibilidade (ignorado).")
    p.add_argument("--data", required=True, help="Data no formato DD-MM-AAAA.")
    p.add_argument("--secao", required=True, help="Seção (DO1, DO2...).")
    p.add_argument("--out", required=True, help="Arquivo JSON de saída.")
    p.add_argument("--mode", choices=["all", "pairs"], default="all", help="Modo de operação.")
    p.add_argument("--map-pairs", action="store_true", help="Atalho legado para --mode pairs.")

    p.add_argument("--open-custom", action="store_true", help="Tenta abrir dropdowns custom para coletar opções.")
    p.add_argument("--raw-options", action="store_true", help="(Mantido) – selects já coletam nativamente.")
    p.add_argument("--verbose-labels", action="store_true", help="Substitui labels genéricas por IDs quando possível.")
    p.add_argument("--auto-disambiguate", action="store_true", help="Desambigua labels duplicadas automaticamente.")

    # Pairs configs
    p.add_argument("--label1-regex")
    p.add_argument("--label2-regex")
    p.add_argument("--id1-regex")
    p.add_argument("--id2-regex")
    p.add_argument("--select1-regex")
    p.add_argument("--select2-regex")
    p.add_argument("--pick1-list")
    p.add_argument("--pick2-list")
    p.add_argument("--limit1", type=int)
    p.add_argument("--limit2", type=int)

    p.add_argument("--poll-timeout-ms", type=int, default=3000)
    p.add_argument("--poll-interval-ms", type=int, default=250)
    p.add_argument("--delay-ms", type=int, default=500)

    p.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    p.add_argument("--headful", action="store_true")
    p.add_argument("--slow-mo", type=int, default=0)

    p.add_argument("--snapshot-html", action="store_true")
    p.add_argument("--no-consent", action="store_true")
    p.add_argument("--include-source-meta", action="store_true")

    p.add_argument("--debug", action="store_true", help="Ativa log DEBUG.")
    return p


class MappingRunner:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.run_id = make_run_id()

    def configure_logging(self):
        if self.args.debug:
            import logging
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug mode ativado.")

    def run(self):
        if discover_dropdown_roots is None:
            raise RuntimeError("Módulo core.dropdown_discovery não encontrado.")
        if DropdownMapperService is None:
            raise RuntimeError("DropdownMapperService não disponível (imports falharam).")

        mode = "pairs" if self.args.map_pairs else self.args.mode
        logger.info("Starting mapping run", extra={"mode": mode, "data": self.args.data, "secao": self.args.secao})
        logger.debug("Service interface", extra={"newInterface": NEW_INTERFACE})

        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser_type = getattr(pw, self.args.browser)
            browser = browser_type.launch(
                headless=not self.args.headful,
                slow_mo=self.args.slow_mo if self.args.headful else 0
            )
            page = browser.new_page()
            url = build_url(self.args.data, self.args.secao)
            logger.info("Navigating", extra={"url": url})

            goto(page, url)

            if not self.args.no_consent:
                try:
                    close_cookies(page)
                except Exception:
                    pass

            if self.args.snapshot_html:
                snapshot_html(page, Path("snapshots"), prefix="mapping")

            frame = page.main_frame
            mapper = DropdownMapperService(frame)

            data_obj: Dict[str, Any] = {}

            if mode == "all":
                dropdowns = self._map_all(mapper)
                if self.args.verbose_labels or self.args.auto_disambiguate:
                    dropdowns = self._apply_verbose_labels(dropdowns)
                data_obj["dropdowns"] = dropdowns

            elif mode == "pairs":
                dropdowns = self._map_all(mapper)
                if self.args.verbose_labels or self.args.auto_disambiguate:
                    dropdowns = self._apply_verbose_labels(dropdowns)
                data_obj["dropdowns"] = dropdowns
                pairs_result = self._map_pairs(mapper)
                data_obj["pairs"] = pairs_result
            else:
                raise ValueError(f"Modo inválido: {mode}")

            browser.close()

        output = self._build_output_payload(mode, data_obj)
        self._write_output(output)
        logger.info("Mapping finished", extra={"mode": mode, "out": self.args.out})

    # ---------- Adaptadores para nova/antiga interface ----------

    def _map_all(self, mapper) -> List[Dict[str, Any]]:
        if NEW_INTERFACE and MapAllConfig:
            cfg = MapAllConfig(
                open_custom=self.args.open_custom,
                filter_sentinels=True
            )
            return mapper.map_all(cfg)
        # Fallback antiga assinatura
        sig = inspect.signature(mapper.map_all)
        if "open_combos" in sig.parameters:
            return mapper.map_all(open_combos=self.args.open_custom)
        # Último recurso: chamar sem args
        return mapper.map_all()

    def _map_pairs(self, mapper) -> Dict[str, Any]:
        if NEW_INTERFACE and MapPairsConfig and PairFilters:
            pcfg = MapPairsConfig(
                label1_regex=self.args.label1_regex,
                label2_regex=self.args.label2_regex,
                id1_regex=self.args.id1_regex,
                id2_regex=self.args.id2_regex,
                delay_ms_after_select=self.args.delay_ms,
                poll_timeout_ms=self.args.poll_timeout_ms,
                poll_interval_ms=self.args.poll_interval_ms,
                open_n2=self.args.open_custom,
                long_poll_until_growth=True
            )
            flt = PairFilters(
                select1_regex=self.args.select1_regex,
                pick1_list=self.args.pick1_list,
                limit1=self.args.limit1,
                select2_regex=self.args.select2_regex,
                pick2_list=self.args.pick2_list,
                limit2_per_n1=self.args.limit2,
                filter_sentinels=True
            )
            return mapper.map_pairs(pcfg, flt)

        # Fallback assinatura antiga
        return mapper.map_pairs(
            label1_regex=self.args.label1_regex,
            label2_regex=self.args.label2_regex,
            select1_regex=self.args.select1_regex,
            pick1_list=self.args.pick1_list,
            limit1=self.args.limit1,
            select2_regex=self.args.select2_regex,
            pick2_list=self.args.pick2_list,
            limit2=self.args.limit2,
            delay_ms=self.args.delay_ms,
            id1_regex=self.args.id1_regex,
            id2_regex=self.args.id2_regex,
            poll_timeout_ms=self.args.poll_timeout_ms,
            poll_interval_ms=self.args.poll_interval_ms,
            keep_placeholders=False,
            open_n2=self.args.open_custom
        )

    # ---------- Payload / Escrita / Labels ----------

    def _build_output_payload(self, mode: str, data_obj: Dict[str, Any]) -> Dict[str, Any]:
        params = {
            "data": self.args.data,
            "secao": self.args.secao,
            "mode": mode,
            "openCustom": self.args.open_custom,
            "rawOptions": self.args.raw_options,
            "verboseLabels": self.args.verbose_labels,
            "autoDisambiguate": self.args.auto_disambiguate,
        }
        if mode == "pairs":
            params.update({
                "label1Regex": self.args.label1_regex,
                "label2Regex": self.args.label2_regex,
                "select1Regex": self.args.select1_regex,
                "select2Regex": self.args.select2_regex,
                "pick1List": self.args.pick1_list,
                "pick2List": self.args.pick2_list,
                "limit1": self.args.limit1,
                "limit2": self.args.limit2,
                "pollTimeoutMs": self.args.poll_timeout_ms,
                "pollIntervalMs": self.args.poll_interval_ms,
                "delayMs": self.args.delay_ms,
            })

        payload = {
            "schema": schema_block("mapping"),
            "source": SOURCES.get("mapping", "mapping-tool") if self.args.include_source_meta else None,
            "runId": self.run_id,
            "generatedAt": utc_now_iso(),
            "params": {k: v for k, v in params.items() if v is not None},
            "data": data_obj
        }
        if payload.get("source") is None:
            payload.pop("source", None)
        return payload

    def _write_output(self, payload: Dict[str, Any]):
        target = normalize_out_path(self.args.out)
        atomic_write_json(target, payload)

    def _apply_verbose_labels(self, dropdowns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        from collections import Counter
        labels = [d.get("label") or "" for d in dropdowns]
        freq = Counter(labels)
        all_same = len(set(labels)) == 1
        out = []
        for idx, d in enumerate(dropdowns, 1):
            lab = d.get("label") or ""
            info = d.get("info") or {}
            attrs = (info.get("attrs") or {}) if isinstance(info, dict) else {}
            cid = attrs.get("id")
            changed = False
            if freq.get(lab, 0) > 1 and cid and self.args.verbose_labels:
                d = {**d, "label": cid}
                changed = True
            elif self.args.auto_disambiguate and freq.get(lab, 0) > 1:
                if cid:
                    d = {**d, "label": cid}
                elif all_same:
                    d = {**d, "label": f"{lab}#{idx}"}
                else:
                    d = {**d, "label": f"{lab}#{idx}"}
                changed = True
            if changed:
                pass
            out.append(d)
        return out


def main(argv: Optional[List[str]] = None):
    parser = create_parser()
    args = parser.parse_args(argv)
    if args.map_pairs:
        args.mode = "pairs"

    runner = MappingRunner(args)
    try:
        runner.configure_logging()
        runner.run()
    except KeyboardInterrupt:
        logger.warning("Interrompido pelo usuário.")
        sys.exit(130)
    except Exception as e:
        logger.exception("Execução falhou (traceback incluído)")
        print(f"[ERRO] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
