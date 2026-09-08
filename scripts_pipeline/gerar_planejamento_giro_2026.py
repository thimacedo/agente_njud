#!/usr/bin/env python3
"""
Gera os arquivos JSON de planejamento para os programas do GIRO (Jan-Ago 2026).
Regra: Programas semanais às quartas-feiras, com janela de 4 a 6 dias de boletins.
"""
import json
import os
from datetime import date, timedelta

# Configurações Base
ANO = 2026
MESES_INICIO = 1  # Janeiro
MESES_FIM = 8     # Agosto
DIA_SEMANA_PROGRAMA = 2  # Quarta-feira (0=Seg, 1=Ter, 2=Qua...)
MIN_BOLETINS = 4
MAX_BOLETINS = 6

def obter_quartas_feiras(inicio_mes, fim_mes):
    """Retorna lista de datas das quartas-feiras no período."""
    quartas = []
    data_atual = date(ANO, inicio_mes, 1)
    data_fim = date(ANO, fim_mes + 1, 1) # Até o primeiro dia do mês seguinte
    
    # Ajusta para a primeira quarta do período
    while data_atual.weekday() != DIA_SEMANA_PROGRAMA:
        data_atual += timedelta(days=1)
    
    while data_atual < data_fim:
        quartas.append(data_atual)
        data_atual += timedelta(days=7)
    
    return quartas

def calcular_janela_boletins(data_programa):
    """
    Calcula a janela de dias para coletar boletins.
    Tenta pegar MAX_BOLETINS dias. Se não der (início do mês), pega o máximo possível >= MIN_BOLETINS.
    Retorna (data_inicio, data_fim, qtd_dias) ou None se inválido.
    """
    # A janela termina no dia do programa (inclusive)
    data_fim = data_programa
    
    # Tenta começar com MAX_BOLETINS dias de antecedência
    dias_antecedencia = MAX_BOLETINS - 1 
    data_inicio = data_fim - timedelta(days=dias_antecedencia)
    
    # Verifica se estamos dentro do ano/mês lógico (opcional, aqui só checo se é data válida)
    # Para o GIRO, geralmente pegamos os dias anteriores consecutivos.
    # Se a data_inicio for muito antiga (ex: antes de jan/2026), ajustamos?
    # Vamos assumir que podemos pegar dias de meses anteriores se necessário para completar a cota,
    # MAS o usuário pediu Jan-Ago. Vamos limitar a start em 01/01/2026 para segurança.
    
    limite_inferior = date(ANO, 1, 1)
    if data_inicio < limite_inferior:
        data_inicio = limite_inferior
    
    qtd_dias = (data_fim - data_inicio).days + 1
    
    if qtd_dias < MIN_BOLETINS:
        return None # Programa inviável (menos de 4 dias disponíveis desde o início do ano)
        
    return data_inicio, data_fim, qtd_dias

def gerar_codigo_programa(data_programa):
    """Gera código no formato MMDD (ex: 0101 para 1º programa de Jan)."""
    # Contar qual número do programa este é dentro do mês
    dia = data_programa.day
    # Aproximação simples: programa 1 se dia <= 7, programa 2 se dia <= 14, etc.
    # Ou melhor: iterar sobre as quartas do mês e contar.
    pass 

def main():
    pasta_saida = "config/planejamento_2026"
    os.makedirs(pasta_saida, exist_ok=True)
    
    quartas = obter_quartas_feiras(MESES_INICIO, MESES_FIM)
    
    programas_por_mes = {}
    
    print(f"--- Gerando Planejamentos GIRO {ANO} ---")
    
    for idx, data_prog in enumerate(quartas):
        janela = calcular_janela_boletins(data_prog)
        
        if not janela:
            print(f"[SKIP] {data_prog} - Janela inválida (< {MIN_BOLETINS} dias)")
            continue
            
        data_ini, data_fim, qtd = janela
        
        # Identificar mês e número do programa no mês
        mes_nome = data_prog.strftime("%B").lower() # janeiro, fevereiro...
        mes_num = data_prog.month
        
        if mes_num not in programas_por_mes:
            programas_por_mes[mes_num] = []
        
        num_programa_no_mes = len(programas_por_mes[mes_num]) + 1
        programas_por_mes[mes_num].append(data_prog)
        
        codigo = f"{mes_num:02d}{num_programa_no_mes:02d}" # Ex: 0101, 0102
        
        config = {
            "programa": "GIRO",
            "codigo": codigo,
            "data_exibicao": str(data_prog),
            "janela_coleta": {
                "inicio": str(data_ini),
                "fim": str(data_fim),
                "dias_totais": qtd
            },
            "parametros": {
                "boletins_minimos": MIN_BOLETINS,
                "corte_por_silencio": True,
                "duracao_silencio_segundos": 1.0,
                "fallback_audio_completo": False, # Regra rígida: se não cortou, falha
                "usar_demucs": False
            },
            "status": "pendente"
        }
        
        # Salvar JSON individual (opcional, mas bom para versionamento)
        # Ou agrupar por mês. Vamos fazer um JSON por PROGRAMA para facilitar a chamada única.
        nome_arquivo = f"giro_{codigo}.json"
        caminho_arquivo = os.path.join(pasta_saida, nome_arquivo)
        
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            
        print(f"[OK] {codigo}: {data_ini} até {data_fim} ({qtd} dias) -> {nome_arquivo}")

    print("\nGeração concluída!")

if __name__ == "__main__":
    main()
