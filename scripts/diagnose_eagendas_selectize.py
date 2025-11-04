"""
Script de diagnóstico detalhado para entender a estrutura dos dropdowns Selectize.
Inspeciona N1, N2 e N3 em diferentes estados.
"""
from __future__ import annotations
import sys
import json
import time
import io
from pathlib import Path

# Forçar UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def inspect_selectize_structure(page):
    """Inspeciona estrutura detalhada dos dropdowns Selectize."""
    
    print("=" * 80)
    print("DIAGNÓSTICO DETALHADO - ESTRUTURA SELECTIZE")
    print("=" * 80)
    
    frame = page.main_frame
    
    print(f"\nPágina: {page.title()}")
    
    input("\n[PAUSA] Verifique se a página carregou. Pressione ENTER...")
    
    print("\n[1/4] Inspecionando estrutura HTML dos dropdowns...")
    
    # Usar JavaScript para inspecionar estrutura completa
    inspection_script = """
    () => {
        const results = [];
        
        // Procurar todos os controles selectize
        const selectizeControls = document.querySelectorAll('.selectize-control');
        
        selectizeControls.forEach((control, index) => {
            const info = {
                index: index,
                classes: control.className,
                isDisabled: control.classList.contains('disabled'),
                innerHTML_length: control.innerHTML.length
            };
            
            // Tentar múltiplas estratégias para encontrar label
            let labelText = null;
            
            // Estratégia 1: label dentro do mesmo container pai
            let parent = control.closest('div.form-group, div.field, div.input-group, div');
            if (parent) {
                let label = parent.querySelector('label');
                if (label) {
                    labelText = label.textContent.trim();
                }
            }
            
            // Estratégia 2: label como irmão anterior
            if (!labelText) {
                let prev = control.previousElementSibling;
                while (prev && !labelText) {
                    if (prev.tagName === 'LABEL') {
                        labelText = prev.textContent.trim();
                    }
                    prev = prev.previousElementSibling;
                }
            }
            
            // Estratégia 3: procurar em qualquer lugar do container pai
            if (!labelText && parent) {
                let allLabels = parent.querySelectorAll('label');
                if (allLabels.length > 0) {
                    labelText = allLabels[0].textContent.trim();
                }
            }
            
            info.label = labelText || 'N/A';
            info.labelSearched = !!labelText;
            
            // Inspecionar input
            const input = control.querySelector('.selectize-input');
            if (input) {
                info.input = {
                    classes: input.className,
                    placeholder: input.getAttribute('placeholder'),
                    text: input.textContent.trim(),
                    childCount: input.children.length,
                    hasDisabledClass: input.classList.contains('disabled'),
                    hasLockedClass: input.classList.contains('locked')
                };
            }
            
            // Inspecionar se há um select oculto
            const selectHidden = control.querySelector('select');
            if (selectHidden) {
                info.hiddenSelect = {
                    id: selectHidden.id || 'N/A',
                    name: selectHidden.name || 'N/A',
                    optionCount: selectHidden.options.length,
                    disabled: selectHidden.disabled,
                    options: Array.from(selectHidden.options).slice(0, 10).map(opt => ({
                        value: opt.value,
                        text: opt.textContent.trim(),
                        disabled: opt.disabled
                    }))
                };
            } else {
                info.hiddenSelect = null;
            }
            
            // Verificar se tem instância Selectize JavaScript
            const selectElem = control.querySelector('select');
            if (selectElem && selectElem.selectize) {
                const sz = selectElem.selectize;
                info.selectizeInstance = {
                    isDisabled: sz.isDisabled || false,
                    isLocked: sz.isLocked || false,
                    optionsCount: Object.keys(sz.options || {}).length,
                    items: sz.items || [],
                    currentValue: sz.getValue ? sz.getValue() : null,
                    settings: {
                        placeholder: sz.settings.placeholder || null,
                        maxItems: sz.settings.maxItems || null
                    }
                };
            } else {
                info.selectizeInstance = null;
            }
            
            results.push(info);
        });
        
        return results;
    }
    """
    
    structure = frame.evaluate(inspection_script)
    
    print(f"\nEncontrados {len(structure)} controles Selectize")
    print("\n" + "=" * 80)
    
    for ctrl in structure:
        print(f"\nControle #{ctrl['index']}")
        print(f"  Label: {ctrl.get('label', 'N/A')}")
        print(f"  Desabilitado: {ctrl.get('isDisabled', False)}")
        print(f"  Classes: {ctrl.get('classes', 'N/A')}")
        
        if ctrl.get('input'):
            inp = ctrl['input']
            print(f"  Input:")
            print(f"    Placeholder: {inp.get('placeholder', 'N/A')}")
            print(f"    Texto: {inp.get('text', 'N/A')[:50]}...")
            print(f"    Children: {inp.get('childCount', 0)}")
        
        if ctrl.get('hiddenSelect'):
            sel = ctrl['hiddenSelect']
            print(f"  Select Oculto:")
            print(f"    ID: {sel.get('id', 'N/A')}")
            print(f"    Name: {sel.get('name', 'N/A')}")
            print(f"    Opções: {sel.get('optionCount', 0)}")
            if sel.get('options'):
                print(f"    Primeiras opções:")
                for opt in sel['options'][:5]:
                    print(f"      - [{opt.get('value')}] {opt.get('text')}")
        
        if ctrl.get('selectizeInstance'):
            inst = ctrl['selectizeInstance']
            print(f"  Instância Selectize:")
            print(f"    Desabilitado: {inst.get('isDisabled', False)}")
            print(f"    Opções carregadas: {inst.get('optionsCount', 0)}")
            print(f"    Valor atual: {inst.get('currentValue', 'N/A')}")
            print(f"    Items: {inst.get('items', [])}")
        
        print("-" * 80)
    
    # Salvar estrutura completa
    output = Path("test_eagendas_selectize_structure.json")
    output.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nEstrutura completa salva em: {output.absolute()}")
    
    input("\n[PAUSA] Analise a estrutura. Pressione ENTER para testar seleção de N1...")
    
    print("\n[2/4] Selecionando primeiro órgão (N1)...")
    
    # Encontrar primeiro selectize
    first_selectize = frame.locator('.selectize-control').first
    if first_selectize.count() > 0:
        input_elem = first_selectize.locator('.selectize-input').first
        
        print("  Abrindo dropdown N1...")
        input_elem.click()
        time.sleep(1.5)
        
        # Coletar opções visíveis
        dropdown = frame.locator('.selectize-dropdown').first
        if dropdown.count() > 0 and dropdown.is_visible():
            options = dropdown.locator('.option').all()
            print(f"  Opções visíveis: {len(options)}")
            
            if len(options) > 0:
                print(f"  Selecionando: {options[0].text_content()}")
                options[0].click()
                time.sleep(2)
    
    input("\n[PAUSA] N1 selecionado. Pressione ENTER para inspecionar N2...")
    
    print("\n[3/4] Inspecionando estado de N2 após seleção de N1...")
    
    # Re-inspecionar estrutura
    structure_after_n1 = frame.evaluate(inspection_script)
    
    print("\nEstado dos controles após selecionar N1:")
    for ctrl in structure_after_n1:
        print(f"\n  {ctrl.get('label', '???')}:")
        print(f"    Desabilitado: {ctrl.get('isDisabled', False)}")
        
        if ctrl.get('hiddenSelect'):
            print(f"    Opções no select oculto: {ctrl['hiddenSelect'].get('optionCount', 0)}")
        
        if ctrl.get('selectizeInstance'):
            inst = ctrl['selectizeInstance']
            print(f"    Opções na instância Selectize: {inst.get('optionsCount', 0)}")
            print(f"    Desabilitado (instância): {inst.get('isDisabled', False)}")
    
    # Salvar estado após N1
    output_after = Path("test_eagendas_selectize_after_n1.json")
    output_after.write_text(json.dumps(structure_after_n1, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nEstado após N1 salvo em: {output_after.absolute()}")
    
    input("\n[PAUSA] Analise as mudanças. Pressione ENTER para tentar abrir N2...")
    
    print("\n[4/4] Tentando abrir dropdown N2...")
    
    # Tentar abrir segundo selectize (N2 - Cargo)
    all_selectize = frame.locator('.selectize-control').all()
    if len(all_selectize) >= 2:
        second_selectize = all_selectize[1]
        input_n2 = second_selectize.locator('.selectize-input').first
        
        print("  Clicando em N2...")
        try:
            input_n2.click()
            time.sleep(1.5)
            
            # Verificar se dropdown abriu
            dropdown_n2 = frame.locator('.selectize-dropdown').first
            if dropdown_n2.count() > 0 and dropdown_n2.is_visible():
                print("  Dropdown N2 ABRIU!")
                options_n2 = dropdown_n2.locator('.option').all()
                print(f"  Opções visíveis: {len(options_n2)}")
                
                for idx, opt in enumerate(options_n2[:10]):
                    print(f"    [{idx+1}] {opt.text_content()}")
            else:
                print("  Dropdown N2 NÃO ABRIU visualmente")
                print("  Verificando no DOM...")
                
                # Verificar se há dropdown no DOM mesmo sem estar visível
                all_dropdowns = frame.locator('.selectize-dropdown').all()
                print(f"  Total de dropdowns no DOM: {len(all_dropdowns)}")
                
                for idx, dd in enumerate(all_dropdowns):
                    is_vis = dd.is_visible()
                    print(f"    Dropdown {idx}: visível={is_vis}")
                    if is_vis:
                        opts = dd.locator('.option').all()
                        print(f"      Opções: {len(opts)}")
                        
        except Exception as e:
            print(f"  Erro ao abrir N2: {e}")
            import traceback
            traceback.print_exc()
    
    input("\n\n[FIM] Pressione ENTER para fechar o navegador...")


if __name__ == '__main__':
    try:
        from dou_snaptrack.utils.browser import launch_browser, new_context, goto, build_url
        
        print("[1/2] Iniciando navegador visível...")
        p, browser = launch_browser(headful=True, slowmo=500)
        
        try:
            print("[2/2] Navegando para e-agendas...")
            context = new_context(browser)
            page = context.new_page()
            page.set_default_timeout(60_000)
            
            url = build_url('eagendas')
            goto(page, url)
            
            # Executar diagnóstico
            inspect_selectize_structure(page)
            
        finally:
            print("\n[Cleanup] Fechando navegador...")
            try:
                browser.close()
            except Exception:
                pass
            try:
                p.stop()
            except Exception:
                pass
                
    except KeyboardInterrupt:
        print("\n\nInterrompido")
        sys.exit(1)
    except Exception as e:
        print(f"\nErro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
