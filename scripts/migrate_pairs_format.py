"""Migra o formato antigo de pairs_DO1_full.json para o novo formato com metadata.

O formato antigo era:
{
  "date": "...",
  "secao": "...",
  "controls": {...},
  "n1_options": [{"n1": {...}, "n2_options": [...]}]
}

O novo formato é:
{
  "_metadata": {
    "secao": "...",
    "data_scrape": "...",
    "timestamp": "...",
    "total_n1": N,
    "total_pairs": N,
    "auto_generated": false,
    "max_age_days": 7
  },
  "pairs": {
    "Órgão 1": ["Sub 1", "Sub 2"],
    "Órgão 2": ["Sub 3"]
  }
}
"""

import json
from datetime import datetime
from pathlib import Path

def migrate_pairs_file(input_path: Path, output_path: Path | None = None):
    """Migra arquivo de formato antigo para novo."""
    
    if output_path is None:
        output_path = input_path.with_suffix(".migrated.json")
    
    # Ler formato antigo
    old_data = json.loads(input_path.read_text(encoding="utf-8"))
    
    # Extrair data e seção
    date_str = old_data.get("date", "")
    secao = old_data.get("secao", "DO1")
    n1_options = old_data.get("n1_options", [])
    
    # Converter para novo formato
    pairs = {}
    for item in n1_options:
        n1_text = item.get("n1", {}).get("text", "")
        n2_options = item.get("n2_options", [])
        
        if n1_text:
            n2_list = []
            for n2_item in n2_options:
                n2_text = n2_item.get("text", "")
                if n2_text:
                    n2_list.append(n2_text)
            
            if n2_list:
                pairs[n1_text] = sorted(n2_list)
    
    # Criar estrutura com metadata
    output = {
        "_metadata": {
            "secao": secao,
            "data_scrape": date_str,
            "timestamp": datetime.now().isoformat(),
            "total_n1": len(pairs),
            "total_pairs": sum(len(n2s) for n2s in pairs.values()),
            "auto_generated": False,
            "max_age_days": 7,
            "migrated_from": str(input_path),
        },
        "pairs": pairs,
    }
    
    # Salvar
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"✅ Migração completa:")
    print(f"   - Origem: {input_path}")
    print(f"   - Destino: {output_path}")
    print(f"   - {output['_metadata']['total_n1']} órgãos (N1)")
    print(f"   - {output['_metadata']['total_pairs']} pares (N1→N2)")
    
    return output

if __name__ == "__main__":
    import sys
    
    input_file = Path("artefatos/pairs_DO1_full.json")
    
    if len(sys.argv) > 1:
        input_file = Path(sys.argv[1])
    
    if not input_file.exists():
        print(f"❌ Arquivo não encontrado: {input_file}")
        sys.exit(1)
    
    # Fazer backup
    backup_path = input_file.with_suffix(".backup.json")
    backup_path.write_text(input_file.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"💾 Backup criado: {backup_path}")
    
    # Migrar e sobrescrever original
    migrate_pairs_file(input_file, input_file)
    
    print("\n✅ Migração concluída! O arquivo original foi atualizado.")
    print(f"   Backup salvo em: {backup_path}")
