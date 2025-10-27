"""Utilitário para atualizar automaticamente o artefato pairs_DO1_full.json.

Este módulo mantém o mapeamento N1→N2 atualizado através de scraping periódico
do site do DOU, garantindo que a UI sempre tenha dados fidedignos.

**IMPORTANTE**: Versão async para compatibilidade com Streamlit/asyncio.

Uso:
    # Atualização manual (CLI)
    python -m dou_snaptrack.utils.pairs_updater

    # Atualização automática via UI (chamado quando TTL expira)
    from dou_snaptrack.utils.pairs_updater import update_pairs_file_if_stale
    update_pairs_file_if_stale()
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Caminho padrão do artefato
DEFAULT_PAIRS_FILE = Path("artefatos") / "pairs_DO1_full.json"

# Idade máxima antes de considerado obsoleto (7 dias)
MAX_AGE_DAYS = 7


def _get_file_age(file_path: Path) -> timedelta | None:
    """Retorna a idade do arquivo baseado em mtime, ou None se não existir."""
    try:
        if not file_path.exists():
            return None
        mtime = file_path.stat().st_mtime
        age = datetime.now() - datetime.fromtimestamp(mtime)
        return age
    except Exception:
        return None


def is_pairs_file_stale(file_path: Path = DEFAULT_PAIRS_FILE, max_age_days: int = MAX_AGE_DAYS) -> bool:
    """Verifica se o arquivo de pares está obsoleto (> max_age_days)."""
    age = _get_file_age(file_path)
    if age is None:
        return True  # Arquivo não existe = obsoleto
    return age > timedelta(days=max_age_days)


# ============================================================================
# VERSÕES ASYNC (para compatibilidade com Streamlit/asyncio)
# ============================================================================

async def update_pairs_file_async(
    file_path: Path = DEFAULT_PAIRS_FILE,
    secao: str = "DO1",
    data: str | None = None,
    limit1: int | None = None,
    limit2: int | None = None,
    headless: bool = True,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """Versão ASYNC de update_pairs_file - compatível com asyncio/Streamlit.

    Args:
        file_path: Caminho do arquivo JSON a atualizar
        secao: Seção do DOU (padrão: DO1)
        data: Data no formato DD-MM-YYYY (padrão: hoje)
        limit1: Limite de órgãos N1 a buscar (None = todos)
        limit2: Limite de N2 por N1 (None = todos)
        headless: Executar browser em modo headless
        progress_callback: Função para reportar progresso (ex: st.progress)

    Returns:
        Dict com estatísticas da atualização: {
            "success": bool,
            "pairs_count": int,
            "n1_count": int,
            "timestamp": str,
            "file": str,
            "error": str | None
        }
    """
    from datetime import date as _date
    from types import SimpleNamespace
    from playwright.async_api import async_playwright
    from dou_snaptrack.cli.plan_live_async import build_plan_live_async

    try:
        # Data padrão = hoje
        if not data:
            data = _date.today().strftime("%d-%m-%Y")

        # Reportar início
        if progress_callback:
            progress_callback(0.1, f"Iniciando atualização para {secao} - {data}...")

        # Executar scraping com async API
        async with async_playwright() as p:
            args = SimpleNamespace(
                secao=secao,
                data=data,
                plan_out=None,  # Não salvar plan, só extrair combos
                select1=None,
                select2=None,
                limit1=limit1,
                limit2=limit2,
                headless=headless,
                slowmo=0,
            )

            if progress_callback:
                progress_callback(0.3, "Scraping site do DOU...")

            cfg = await build_plan_live_async(p, args)

        # Extrair pares únicos
        combos = cfg.get("combos", [])
        if not combos:
            return {
                "success": False,
                "pairs_count": 0,
                "n1_count": 0,
                "timestamp": datetime.now().isoformat(),
                "file": str(file_path),
                "error": "Nenhum combo encontrado no scraping",
            }

        # Agrupar por N1
        pairs: dict[str, list[str]] = {}
        for combo in combos:
            n1 = combo.get("key1", "")
            n2 = combo.get("key2", "")
            if n1 and n2:
                if n1 not in pairs:
                    pairs[n1] = []
                if n2 not in pairs[n1]:
                    pairs[n1].append(n2)

        # Ordenar para consistência
        for n1 in pairs:
            pairs[n1] = sorted(pairs[n1])

        if progress_callback:
            progress_callback(0.7, f"Encontrados {len(pairs)} órgãos...")

        # Criar estrutura final
        output = {
            "_metadata": {
                "secao": secao,
                "data_scrape": data,
                "timestamp": datetime.now().isoformat(),
                "total_n1": len(pairs),
                "total_pairs": sum(len(n2s) for n2s in pairs.values()),
                "auto_generated": True,
                "max_age_days": MAX_AGE_DAYS,
            },
            "pairs": pairs,
        }

        # Salvar arquivo
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

        if progress_callback:
            progress_callback(1.0, "Atualização concluída!")

        return {
            "success": True,
            "pairs_count": output["_metadata"]["total_pairs"],
            "n1_count": output["_metadata"]["total_n1"],
            "timestamp": output["_metadata"]["timestamp"],
            "file": str(file_path),
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "pairs_count": 0,
            "n1_count": 0,
            "timestamp": datetime.now().isoformat(),
            "file": str(file_path),
            "error": f"{type(e).__name__}: {e}",
        }


# ============================================================================
# VERSÕES SYNC (para CLI e retrocompatibilidade)
# ============================================================================

def update_pairs_file(
    file_path: Path = DEFAULT_PAIRS_FILE,
    secao: str = "DO1",
    data: str | None = None,
    limit1: int | None = None,
    limit2: int | None = None,
    headless: bool = True,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """Versão SYNC (CLI) - wrapper que executa a versão async.

    NOTA: Esta função usa asyncio.run() para executar a versão async.
    Não deve ser chamada dentro de um loop asyncio ativo (use update_pairs_file_async diretamente).

    Args:
        file_path: Caminho do arquivo JSON a atualizar
        secao: Seção do DOU (padrão: DO1)
        data: Data no formato DD-MM-YYYY (padrão: hoje)
        limit1: Limite de órgãos N1 a buscar (None = todos)
        limit2: Limite de N2 por N1 (None = todos)
        headless: Executar browser em modo headless
        progress_callback: Função para reportar progresso (ex: st.progress)

    Returns:
        Dict com estatísticas da atualização
    """
    return asyncio.run(
        update_pairs_file_async(
            file_path=file_path,
            secao=secao,
            data=data,
            limit1=limit1,
            limit2=limit2,
            headless=headless,
            progress_callback=progress_callback,
        )
    )


def update_pairs_file_if_stale(
    file_path: Path = DEFAULT_PAIRS_FILE,
    max_age_days: int = MAX_AGE_DAYS,
    **kwargs,
) -> dict[str, Any] | None:
    """Atualiza o arquivo de pares apenas se estiver obsoleto.

    Args:
        file_path: Caminho do arquivo JSON
        max_age_days: Idade máxima em dias antes de considerar obsoleto
        **kwargs: Argumentos passados para update_pairs_file()

    Returns:
        Dict com resultado da atualização, ou None se arquivo ainda estava válido
    """
    if not is_pairs_file_stale(file_path, max_age_days):
        return None  # Arquivo ainda está fresco

    return update_pairs_file(file_path, **kwargs)


def get_pairs_file_info(file_path: Path = DEFAULT_PAIRS_FILE) -> dict[str, Any]:
    """Retorna informações sobre o arquivo de pares atual.

    Returns:
        {
            "exists": bool,
            "age_days": float | None,
            "is_stale": bool,
            "last_update": str | None,
            "n1_count": int | None,
            "pairs_count": int | None,
            "metadata": dict | None
        }
    """
    try:
        exists = file_path.exists()
        age = _get_file_age(file_path)
        age_days = age.total_seconds() / 86400 if age else None
        is_stale = is_pairs_file_stale(file_path)

        metadata = None
        n1_count = None
        pairs_count = None
        last_update = None

        if exists:
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                metadata = data.get("_metadata", {})
                last_update = metadata.get("timestamp")
                n1_count = metadata.get("total_n1")
                pairs_count = metadata.get("total_pairs")
            except Exception:
                pass

        return {
            "exists": exists,
            "age_days": age_days,
            "is_stale": is_stale,
            "last_update": last_update,
            "n1_count": n1_count,
            "pairs_count": pairs_count,
            "metadata": metadata,
        }
    except Exception:
        return {
            "exists": False,
            "age_days": None,
            "is_stale": True,
            "last_update": None,
            "n1_count": None,
            "pairs_count": None,
            "metadata": None,
        }


def main():
    """CLI para atualização manual do arquivo de pares."""
    import argparse

    parser = argparse.ArgumentParser(description="Atualizar artefato pairs_DO1_full.json")
    parser.add_argument("--file", type=Path, default=DEFAULT_PAIRS_FILE, help="Caminho do arquivo")
    parser.add_argument("--secao", default="DO1", help="Seção do DOU")
    parser.add_argument("--data", help="Data no formato DD-MM-YYYY (padrão: hoje)")
    parser.add_argument("--limit1", type=int, help="Limite de órgãos N1")
    parser.add_argument("--limit2", type=int, help="Limite de N2 por N1")
    parser.add_argument("--headful", action="store_true", help="Mostrar browser")
    parser.add_argument("--force", action="store_true", help="Forçar atualização mesmo se não obsoleto")
    parser.add_argument("--info", action="store_true", help="Apenas mostrar informações do arquivo")

    args = parser.parse_args()

    if args.info:
        info = get_pairs_file_info(args.file)
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return

    if not args.force and not is_pairs_file_stale(args.file):
        print(f"✓ Arquivo {args.file} ainda está atualizado (< {MAX_AGE_DAYS} dias)")
        print("  Use --force para atualizar mesmo assim")
        return

    # CORREÇÃO CRÍTICA: Limpar loop asyncio antes de Playwright Sync
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop and not loop.is_closed():
            loop.close()
    except RuntimeError:
        pass
    asyncio.set_event_loop(asyncio.new_event_loop())

    print(f"🔄 Atualizando {args.file}...")
    result = update_pairs_file(
        file_path=args.file,
        secao=args.secao,
        data=args.data,
        limit1=args.limit1,
        limit2=args.limit2,
        headless=not args.headful,
        progress_callback=lambda p, msg: print(f"  [{int(p*100):3d}%] {msg}"),
    )

    if result["success"]:
        print(f"✅ Sucesso!", file=sys.stderr)
        print(f"   - {result['n1_count']} órgãos (N1)", file=sys.stderr)
        print(f"   - {result['pairs_count']} pares (N1→N2)", file=sys.stderr)
        print(f"   - Salvo em: {result['file']}", file=sys.stderr)
        print(f"   - Timestamp: {result['timestamp']}", file=sys.stderr)
        # Output JSON no stdout para consumo programático
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"❌ Erro: {result['error']}", file=sys.stderr)
        # Output JSON no stdout para consumo programático
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
