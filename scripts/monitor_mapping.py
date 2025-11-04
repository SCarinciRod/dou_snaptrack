"""
Monitor do progresso do mapeamento completo E-AGENDAS.

Exibe estatísticas em tempo real do arquivo de log.
"""
from pathlib import Path
import time
import re
import sys

def parse_log(log_file):
    """Extrai estatísticas do log."""
    if not log_file.exists():
        return None
    
    content = log_file.read_text(encoding='utf-8', errors='replace')
    
    stats = {
        'orgaos_total': None,
        'orgao_atual': None,
        'cargo_atual': None,
        'cargos_total': 0,
        'agentes_total': 0,
        'completed': False,
        'error': None
    }
    
    # Total de órgãos encontrados
    match = re.search(r'Encontrados (\d+) órgãos', content)
    if match:
        stats['orgaos_total'] = int(match.group(1))
    
    # Órgão sendo processado (pegar último)
    matches = re.findall(r'\[(\d+)/(\d+)\] Processando: (.+)', content)
    if matches:
        last = matches[-1]
        stats['orgao_atual'] = int(last[0])
        stats['orgaos_total'] = int(last[1])
    
    # Total de cargos
    match = re.search(r'Total de cargos: (\d+)', content)
    if match:
        stats['cargos_total'] = int(match.group(1))
    
    # Total de agentes
    match = re.search(r'Total de agentes: (\d+)', content)
    if match:
        stats['agentes_total'] = int(match.group(1))
    
    # Verificar se completou
    if 'MAPEAMENTO CONCLUÍDO COM SUCESSO' in content:
        stats['completed'] = True
    
    # Verificar erro
    if 'Traceback' in content or 'Error' in content or 'erro' in content.lower():
        error_lines = [l for l in content.split('\n') if 'error' in l.lower() or 'traceback' in l.lower()]
        if error_lines:
            stats['error'] = error_lines[-1][:100]
    
    return stats


def format_time(seconds):
    """Formata segundos em HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main():
    log_file = Path("logs/map_eagendas_full.log")
    
    print("=" * 80)
    print("MONITOR DE PROGRESSO - MAPEAMENTO E-AGENDAS")
    print("=" * 80)
    print(f"\nArquivo de log: {log_file.absolute()}")
    print("\nAtualizando a cada 10 segundos... (Ctrl+C para sair)")
    print("\n" + "-" * 80)
    
    start_time = time.time()
    last_orgao = 0
    
    try:
        while True:
            stats = parse_log(log_file)
            
            # Limpar tela (somente no Windows)
            # print('\033[2J\033[H', end='')
            
            elapsed = time.time() - start_time
            
            print(f"\n[{time.strftime('%H:%M:%S')}] Tempo decorrido: {format_time(elapsed)}")
            print("-" * 80)
            
            if not stats:
                print("⏳ Aguardando início do mapeamento...")
            elif stats['completed']:
                print("✅ MAPEAMENTO CONCLUÍDO!")
                print(f"\n📊 Estatísticas Finais:")
                print(f"   Órgãos processados: {stats['orgaos_total']}")
                print(f"   Total de cargos: {stats['cargos_total']}")
                print(f"   Total de agentes: {stats['agentes_total']}")
                print(f"   Tempo total: {format_time(elapsed)}")
                break
            elif stats['error']:
                print(f"❌ ERRO DETECTADO!")
                print(f"   {stats['error']}")
                print(f"\n   Verifique o log completo em: {log_file.absolute()}")
                break
            else:
                if stats['orgao_atual']:
                    progress = (stats['orgao_atual'] / stats['orgaos_total']) * 100
                    print(f"📍 Progresso: {stats['orgao_atual']}/{stats['orgaos_total']} órgãos ({progress:.1f}%)")
                    
                    # Estimar tempo restante
                    if stats['orgao_atual'] > last_orgao:
                        rate = stats['orgao_atual'] / elapsed  # órgãos por segundo
                        remaining_orgaos = stats['orgaos_total'] - stats['orgao_atual']
                        eta_seconds = remaining_orgaos / rate if rate > 0 else 0
                        print(f"⏱️  Tempo estimado restante: {format_time(eta_seconds)}")
                        last_orgao = stats['orgao_atual']
                
                print(f"\n📊 Estatísticas Parciais:")
                if stats['orgaos_total']:
                    print(f"   Total de órgãos: {stats['orgaos_total']}")
                if stats['cargos_total']:
                    print(f"   Cargos mapeados: {stats['cargos_total']}")
                if stats['agentes_total']:
                    print(f"   Agentes públicos: {stats['agentes_total']}")
            
            print("\n" + "-" * 80)
            print("(Atualizando em 10 segundos...)")
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitor interrompido pelo usuário")
        print(f"   O mapeamento continua rodando em segundo plano")
        print(f"   Para ver o log: type {log_file.absolute()}")


if __name__ == '__main__':
    main()
