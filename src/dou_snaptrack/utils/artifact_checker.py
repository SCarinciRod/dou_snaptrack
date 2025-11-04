"""
Verificador de idade do artefato e-agendas.

Verifica se o artefato existe e está atualizado.
Usado pela UI para decidir se precisa atualizar.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta
import json


def check_artifact_age(artifact_path: str | Path | None = None) -> dict:
    """
    Verifica idade do artefato.
    
    Args:
        artifact_path: Caminho do artefato (None = latest)
    
    Returns:
        Dict com:
        {
            "exists": bool,
            "path": str,
            "age_days": int,
            "last_update": str (ISO),
            "needs_update": bool,
            "is_stale": bool,  # > 30 dias
            "is_critical": bool,  # > 60 dias
            "stats": dict,
            "message": str
        }
    """
    if artifact_path is None:
        # Procurar a partir do diretório raiz do projeto
        # __file__ = .../src/dou_snaptrack/utils/artifact_checker.py
        # Precisamos subir 3 níveis: utils -> dou_snaptrack -> src -> projeto
        module_dir = Path(__file__).parent.parent.parent.parent
        artifact_path = module_dir / "artefatos" / "pairs_eagendas_latest.json"
    
    artifact_path = Path(artifact_path)
    
    result = {
        "exists": False,
        "path": str(artifact_path.absolute()),
        "age_days": None,
        "last_update": None,
        "needs_update": True,
        "is_stale": False,
        "is_critical": False,
        "stats": None,
        "message": ""
    }
    
    # Verificar se existe
    if not artifact_path.exists():
        result["message"] = "Artefato não encontrado. Execute: python scripts/update_eagendas_artifact.py"
        return result
    
    result["exists"] = True
    
    # Ler metadata
    try:
        data = json.loads(artifact_path.read_text(encoding='utf-8'))
        
        # Extrair data da última atualização
        last_update_str = None
        
        # Tentar update_info primeiro
        if "update_info" in data and "update_date" in data["update_info"]:
            last_update_str = data["update_info"]["update_date"]
        # Fallback: timestamp
        elif "timestamp" in data:
            last_update_str = data["timestamp"]
        
        if last_update_str:
            # Parse ISO ou formato customizado
            try:
                last_update = datetime.fromisoformat(last_update_str)
            except:
                # Tentar formato "%Y-%m-%d %H:%M:%S"
                try:
                    last_update = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M:%S")
                except:
                    last_update = None
            
            if last_update:
                result["last_update"] = last_update.isoformat()
                
                # Calcular idade
                now = datetime.now()
                age = now - last_update
                result["age_days"] = age.days
                
                # Classificar
                if age.days <= 30:
                    result["needs_update"] = False
                    result["message"] = f"Artefato atualizado ({age.days} dias)"
                elif age.days <= 60:
                    result["needs_update"] = True
                    result["is_stale"] = True
                    result["message"] = f"Artefato desatualizado ({age.days} dias). Recomenda-se atualizar."
                else:
                    result["needs_update"] = True
                    result["is_stale"] = True
                    result["is_critical"] = True
                    result["message"] = f"Artefato CRÍTICO ({age.days} dias). ATUALIZAÇÃO URGENTE!"
        
        # Extrair stats
        if "stats" in data:
            result["stats"] = data["stats"]
    
    except Exception as e:
        result["message"] = f"Erro ao ler artefato: {e}"
    
    return result


def print_artifact_status(status: dict | None = None):
    """Imprime status formatado do artefato."""
    if status is None:
        status = check_artifact_age()
    
    print("=" * 80)
    print("STATUS DO ARTEFATO E-AGENDAS")
    print("=" * 80)
    
    if not status["exists"]:
        print("\n❌ ARTEFATO NÃO ENCONTRADO")
        print(f"\n{status['message']}")
    else:
        # Status visual
        if not status["needs_update"]:
            icon = "✅"
            color_label = "ATUALIZADO"
        elif status["is_critical"]:
            icon = "🔴"
            color_label = "CRÍTICO"
        elif status["is_stale"]:
            icon = "⚠️"
            color_label = "DESATUALIZADO"
        else:
            icon = "ℹ️"
            color_label = "INFORMAÇÃO"
        
        print(f"\n{icon} Status: {color_label}")
        print(f"\n📁 Arquivo: {Path(status['path']).name}")
        
        if status["last_update"]:
            last_update_dt = datetime.fromisoformat(status["last_update"])
            print(f"📅 Última atualização: {last_update_dt.strftime('%d/%m/%Y %H:%M:%S')}")
        
        if status["age_days"] is not None:
            print(f"⏱️  Idade: {status['age_days']} dias")
        
        if status["stats"]:
            print(f"\n📊 Estatísticas:")
            print(f"   Órgãos: {status['stats'].get('total_orgaos', 0)}")
            print(f"   Cargos: {status['stats'].get('total_cargos', 0)}")
            print(f"   Agentes: {status['stats'].get('total_agentes', 0)}")
        
        print(f"\n💬 {status['message']}")
        
        if status["needs_update"]:
            print(f"\n🔄 Para atualizar:")
            print(f"   python scripts/update_eagendas_artifact.py")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    # Teste
    status = check_artifact_age()
    print_artifact_status(status)
