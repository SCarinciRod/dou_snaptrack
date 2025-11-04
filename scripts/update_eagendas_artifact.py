"""
Script de atualização automática do artefato de pares e-agendas.

ESTRATÉGIA:
- Roda mensalmente (agendado via Task Scheduler)
- Gera novo artefato completo
- Mantém histórico de versões
- Notifica via log se falhar

USO:
- Manual: python scripts/update_eagendas_artifact.py
- Automático: Task Scheduler (configurar com setup_monthly_update.ps1)
"""
from __future__ import annotations
import sys
import json
import io
from pathlib import Path
from datetime import datetime
import logging
import shutil

# Forçar UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dou_snaptrack.utils.browser import launch_browser, new_context, goto, build_url
from dou_snaptrack.mappers.eagendas_pairs_fast import map_eagendas_pairs_fast

# Setup logging
LOG_DIR = Path(__file__).parent.parent / "logs" / "artifact_updates"
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_file = LOG_DIR / f"update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def update_artifact():
    """Executa atualização mensal do artefato."""
    logger.info("=" * 80)
    logger.info("ATUALIZAÇÃO MENSAL DO ARTEFATO E-AGENDAS")
    logger.info("=" * 80)
    logger.info(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_time = datetime.now()
    
    # Diretórios
    ARTIFACT_DIR = Path(__file__).parent.parent / "artefatos"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    
    ARCHIVE_DIR = ARTIFACT_DIR / "archive"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Arquivos
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    year_month = datetime.now().strftime("%Y%m")
    
    new_artifact = ARTIFACT_DIR / f"pairs_eagendas_{timestamp}.json"
    latest_artifact = ARTIFACT_DIR / "pairs_eagendas_latest.json"
    monthly_artifact = ARCHIVE_DIR / f"pairs_eagendas_{year_month}.json"
    
    try:
        # [1] Backup do artefato atual (se existir)
        if latest_artifact.exists():
            logger.info("[1/5] Fazendo backup do artefato atual...")
            backup_file = ARCHIVE_DIR / f"pairs_eagendas_backup_{timestamp}.json"
            shutil.copy2(latest_artifact, backup_file)
            logger.info(f"  Backup salvo: {backup_file.name}")
        else:
            logger.info("[1/5] Nenhum artefato anterior encontrado")
        
        # [2] Iniciar navegador
        logger.info("[2/5] Iniciando navegador (modo headless)...")
        p, browser = launch_browser(headful=False, slowmo=0)
        
        try:
            context = new_context(browser)
            page = context.new_page()
            page.set_default_timeout(5000)  # Timeout 5s
            
            # [3] Navegar
            logger.info("[3/5] Navegando para e-agendas...")
            url = build_url('eagendas')
            goto(page, url)
            
            # [4] Mapear
            logger.info("[4/5] Iniciando mapeamento completo OTIMIZADO...")
            logger.info("  ⏱️  Tempo estimado: 5-15 minutos (30x mais rápido!)")
            logger.info("")
            
            result = map_eagendas_pairs_fast(
                page=page,
                limit_orgaos=None,  # TODOS
                limit_cargos_per_orgao=None,  # TODOS
                verbose=True
            )
            
            # [5] Salvar
            logger.info("[5/5] Salvando resultados...")
            
            # Adicionar metadata
            result["update_info"] = {
                "update_date": datetime.now().isoformat(),
                "update_type": "monthly_automatic",
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "log_file": str(log_file.absolute())
            }
            
            # Salvar timestamped
            new_artifact.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            logger.info(f"  ✅ Artefato timestamped: {new_artifact.name}")
            
            # Salvar mensal (sobrescreve se já existe no mesmo mês)
            monthly_artifact.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            logger.info(f"  ✅ Artefato mensal: {monthly_artifact.name}")
            
            # Atualizar latest
            latest_artifact.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            logger.info(f"  ✅ Latest atualizado: {latest_artifact.name}")
            
            # Estatísticas
            elapsed = (datetime.now() - start_time).total_seconds()
            elapsed_min = elapsed / 60
            elapsed_hr = elapsed / 3600
            
            stats = result.get("stats", {})
            
            logger.info("")
            logger.info("=" * 80)
            logger.info("ATUALIZAÇÃO CONCLUÍDA COM SUCESSO!")
            logger.info("=" * 80)
            logger.info(f"  Tempo total: {elapsed_hr:.1f}h ({elapsed_min:.0f} min)")
            logger.info(f"  Órgãos processados: {stats.get('total_orgaos', 0)}")
            logger.info(f"  Cargos mapeados: {stats.get('total_cargos', 0)}")
            logger.info(f"  Agentes públicos: {stats.get('total_agentes', 0)}")
            logger.info(f"  Órgãos sem cargos: {stats.get('orgaos_sem_cargos', 0)}")
            logger.info(f"  Cargos sem agentes: {stats.get('cargos_sem_agentes', 0)}")
            logger.info("")
            logger.info("PRÓXIMA ATUALIZAÇÃO: ~30 dias")
            logger.info("=" * 80)
            
            return True
            
        finally:
            logger.info("Fechando navegador...")
            try:
                browser.close()
            except Exception:
                pass
            try:
                p.stop()
            except Exception:
                pass
    
    except KeyboardInterrupt:
        logger.warning("Atualização interrompida pelo usuário")
        return False
    except Exception as e:
        logger.error(f"ERRO durante atualização: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Ponto de entrada."""
    success = update_artifact()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
