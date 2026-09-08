# coding: utf-8
"""
Planejamento dos 4 programas do GIRO de Janeiro 2026.

Gera JSON com metadados completos para cada programa:
- mmss: código do programa
- data_terça: data de exibição
- período das notícias (segunda a domingo)
- pasta de origem dos boletins
- nome do arquivo de saída esperado
"""

import json
from pathlib import Path
from src.giro.utils import gerar_plano, terça_do_programa, nome_programa


def planejar_giro_janeiro_2026() -> dict:
    """Gera o planejamento completo dos 4 programas do GIRO de janeiro 2026."""
    
    # Filtrar programas cujos boletins são de janeiro (mes_boletim = 1)
    todos_programas = gerar_plano(2026)
    programas_janeiro = [p for p in todos_programas if p['mes_boletim'] == 1]
    
    # Validar: devem ser exatamente 4 programas
    assert len(programas_janeiro) == 4, f"Esperado 4 programas, encontrado {len(programas_janeiro)}"
    
    plano_completo = {
        "programa": "GIRO",
        "mes_referencia": "JANEIRO",
        "ano": 2026,
        "total_programas": 4,
        "pasta_base_boletins": r"H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\01_BOLETINS_DIARIOS\03_AUDIOS_RADIO\01 - JAN - 26",
        "padrao_nomeclatura_saida": "GNC_mmss_DD-MM-AA.mp3",
        "programas": []
    }
    
    for i, prog in enumerate(programas_janeiro, 1):
        mmss = prog['mmss']
        data_terca = prog['data_terça']
        
        # Converter data para formato DD-MM-AA
        from datetime import datetime
        dt = datetime.fromisoformat(data_terca)
        data_formatada = dt.strftime("%d-%m-%y")
        
        # Nome do arquivo de saída
        nome_saida = nome_programa(mmss, data_formatada)
        
        # Padrão de busca dos boletins na pasta
        # Ex: BOLETIM_RADIO_TJRN_*_JAN_2026*.mp3 ou por data específica
        padrao_busca = f"BOLETIM_RADIO_TJRN_*_{prog['seg_notícias']}_{prog['dom_notícias']}*.mp3"
        
        programa_meta = {
            "ordem": i,
            "mmss": mmss,
            "data_exibicao": data_terca,
            "data_formatada": data_formatada,
            "periodo_noticias": {
                "segunda": prog['seg_notícias'],
                "domingo": prog['dom_notícias'],
                "dias_uteis": 5  # seg a sex
            },
            "nome_arquivo_saida": nome_saida,
            "pasta_boletins": plano_completo["pasta_base_boletins"],
            "padrao_busca_boletins": padrao_busca,
            "previsao_noticias": prog['n_noticias_previsto'],
            "status": "PENDENTE",
            "observacoes": []
        }
        
        # Adicionar observações específicas
        if i == 1:
            programa_meta["observacoes"].append("Primeiro programa do ano - validar vinhetas de abertura/encerramento")
        if i == 4:
            programa_meta["observacoes"].append("Último programa com boletins de janeiro - atenção ao fechamento do mês")
        
        plano_completo["programas"].append(programa_meta)
    
    return plano_completo


def salvar_plano(plano: dict, caminho: Path) -> None:
    """Salva o plano em formato JSON."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(plano, f, indent=2, ensure_ascii=False)
    print(f"Plano salvo em: {caminho}")


if __name__ == "__main__":
    plano = planejar_giro_janeiro_2026()
    
    # Exibir resumo
    print("=" * 80)
    print("PLANEJAMENTO GIRO - JANEIRO 2026")
    print("=" * 80)
    print()
    print(f"Total de programas: {plano['total_programas']}")
    print(f"Mês dos boletins: {plano['mes_referencia']}")
    print(f"Pasta base: {plano['pasta_base_boletins']}")
    print()
    
    for prog in plano['programas']:
        print(f"--- PROGRAMA {prog['ordem']}: {prog['mmss']} ---")
        print(f"  Exibição: {prog['data_exibicao']} ({prog['data_formatada']})")
        print(f"  Notícias: {prog['periodo_noticias']['segunda']} a {prog['periodo_noticias']['domingo']}")
        print(f"  Saída: {prog['nome_arquivo_saida']}")
        print(f"  Previsão: {prog['previsao_noticias']} notícias")
        if prog['observacoes']:
            print(f"  Obs: {'; '.join(prog['observacoes'])}")
        print()
    
    # Salvar em disco
    output_path = Path("/workspace/data/plano_giro_janeiro_2026.json")
    salvar_plano(plano, output_path)
    
    print("✅ Planejamento concluído!")
