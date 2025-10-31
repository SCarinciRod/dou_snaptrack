"""Script de teste para verificar atualização de pairs sem Streamlit."""

import sys
from pathlib import Path

# Add src to path
SRC_ROOT = Path(__file__).parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

def test_pairs_update():
    """Testa atualização de pairs sem asyncio loop."""
    from dou_snaptrack.utils.pairs_updater import update_pairs_file
    
    print("=" * 60)
    print("TESTE: Atualização de pairs_DO1_full.json")
    print("=" * 60)
    
    def progress_callback(progress, message):
        print(f"[{progress*100:5.1f}%] {message}")
    
    result = update_pairs_file(
        limit1=3,  # Apenas 3 N1 para teste rápido
        limit2=5,  # Apenas 5 N2 por N1
        progress_callback=progress_callback
    )
    
    print("\n" + "=" * 60)
    print("RESULTADO:")
    print("=" * 60)
    
    if result["success"]:
        print(f"✅ SUCESSO!")
        print(f"   Órgãos N1: {result['n1_count']}")
        print(f"   Total pares: {result['pairs_count']}")
        print(f"   Arquivo: {result['file']}")
        print(f"   Timestamp: {result['timestamp']}")
    else:
        print(f"❌ FALHA!")
        print(f"   Erro: {result['error']}")
    
    print("=" * 60)
    return result["success"]

if __name__ == "__main__":
    success = test_pairs_update()
    sys.exit(0 if success else 1)
