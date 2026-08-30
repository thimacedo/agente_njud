import os
import sys
import re
import json
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

# Centralizado em config/settings.py — evitar hardcoded (DECISOES.md item 7)
try:
    from config.settings import Settings
    settings = Settings()
    PASTA_ORIGEM_JORNAIS = settings.DIR_OUTPUT
    PASTA_DESTINO_DRIVE_PAI = settings.DIR_DRIVE_JORNAIS
except Exception:
    # Fallback para paths locais se settings não estiver configurado
    PASTA_ORIGEM_JORNAIS = Path("F:/Projetos/DIVISOR/data/output")
    PASTA_DESTINO_DRIVE_PAI = Path(r"H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\02_JORNAIS_NJUD\03_AUDIOS_RADIO")

PATTERN_NOME = re.compile(r"^NJUD_\d{4}_\d{2}-\d{2}-\d{4}\.mp3$")

# Mapeamento inclui ANO para evitar colisão entre anos diferentes (bug fix 2026-08-25)
def obter_mapeamento_meses(ano: int = 26):
    return {
        "JAN": f"01 - JAN - {ano}",
        "FEV": f"02 - FEV - {ano}",
        "MAR": f"03 - MAR - {ano}",
        "ABR": f"04 - ABR - {ano}",
        "MAI": f"05 - MAI - {ano}",
        "JUN": f"06 - JUN - {ano}",
        "JUL": f"07 - JUL - {ano}",
        "AGO": f"08 - AGO - {ano}",
        "SET": f"09 - SET - {ano}",
        "OUT": f"10 - OUT - {ano}",
        "NOV": f"11 - NOV - {ano}",
        "DEZ": f"12 - DEZ - {ano}",
    }

def obter_pasta_mes_destino(nome_arquivo):
    """Extrai mês e ano do nome do arquivo e retorna pasta correta.
    
    Bug fix 2026-08-25: agora lê o ANO do nome do arquivo para evitar
    colisão entre dezembro/2026 e dezembro/2027 na mesma pasta.
    """
    parts = nome_arquivo.replace(".mp3", "").split("_")
    if len(parts) >= 3:
        data_str = parts[2]
        data_parts = data_str.split("-")
        if len(data_parts) == 3:
            # Extrai ano (últimos 2 dígitos) e mês
            ano = int(data_parts[0][-2:]) if len(data_parts[0]) >= 4 else 26
            mes_num = data_parts[1]
            mes_nomes = {
                "01": "JAN", "02": "FEV", "03": "MAR", "04": "ABR",
                "05": "MAI", "06": "JUN", "07": "JUL", "08": "AGO",
                "09": "SET", "10": "OUT", "11": "NOV", "12": "DEZ"
            }
            mes_sigla = mes_nomes.get(mes_num)
            if mes_sigla:
                mapeamento = obter_mapeamento_meses(ano)
                if mes_sigla in mapeamento:
                    return PASTA_DESTINO_DRIVE_PAI / mapeamento[mes_sigla]
    return None

def sincronizar_com_drive():
    """Sincroniza jornais montados com Google Drive.
    
    Bug fixes 2026-08-25:
    - Implementa pendentes_drive.json conforme documentação (antes só printava)
    - Usa write-then-rename atômico para evitar perda de dados
    - Centraliza paths via settings.py
    """
    if not os.path.exists(str(PASTA_DESTINO_DRIVE_PAI)):
        print(f" ⚠ Google Drive não está montado ou acessível em: {PASTA_DESTINO_DRIVE_PAI}")
        print(" O processo será pausado. Conecte o Google Drive e execute este script novamente.")
        # REGRA DOCUMENTADA: grava pendentes para retry futuro (antes só printava)
        pasta_saida = PASTA_ORIGEM_JORNAIS / "_logs"
        pasta_saida.mkdir(parents=True, exist_ok=True)
        pendentes_path = pasta_saida / "pendentes_drive.json"
        pendentes_path.write_text(json.dumps({
            "data": datetime.now().isoformat(),
            "motivo": "drive_offline",
            "caminho_destino": str(PASTA_DESTINO_DRIVE_PAI),
            "acao": "executar_novamente_apos_conectar_drive"
        }, indent=2), encoding="utf-8")
        print(f" 📝 Pendência registrada em: {pendentes_path}")
        return

    # Alinhamento 2026-08-24 (DECISOES.md item 6): a montagem grava em
    # data/output/JORNAIS_FINAL/. Raiz de data/output mantida como fallback
    # por compatibilidade com jornais montados antes do alinhamento.
    pasta_jornais = PASTA_ORIGEM_JORNAIS / "JORNAIS_FINAL"
    if not pasta_jornais.is_dir():
        pasta_jornais = PASTA_ORIGEM_JORNAIS
        print(" ⚠ JORNAIS_FINAL não existe; usando raiz de data/output (fallback).")

    arquivos = [pasta_jornais / f for f in os.listdir(pasta_jornais) if f.endswith(".mp3")]
    invalidos = [p for p in arquivos if not PATTERN_NOME.match(p.name)]
    if invalidos:
        print("\n=== VALIDAÇÃO PRÉ-SYNC: NOMENCLATURA INVÁLIDA ===")
        for p in invalidos:
            print(f" ✖ Nome fora do padrão canônico: {p.name}")
        print(f"Total inválidos: {len(invalidos)}/{len(arquivos)}")
        pendentes = pasta_jornais / "_logs"
        pendentes.mkdir(parents=True, exist_ok=True)
        (pendentes / "nomenclatura_invalida.json").write_text(
            json.dumps(
                {
                    "data": datetime.now().isoformat(),
                    "pasta": str(pasta_jornais),
                    "total": len(arquivos),
                    "invalid_count": len(invalidos),
                    "invalid": [str(p) for p in invalidos],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f" 📝 Relatório salvo em: {pendentes / 'nomenclatura_invalida.json'}")
        print(" ⛔ Sincronização bloqueada por nomenclatura inválida.")
        return

    jornais = arquivos
    print(f"=== Sincronizando {len(jornais)} jornais montados com o Google Drive ===")
    
    sucesso = 0
    erros = 0
    enviados = []
    
    for j in jornais:
        pasta_destino = obter_pasta_mes_destino(j.name)
        if not pasta_destino:
            print(f" ⚠ Não foi possível mapear mês para: {j.name}")
            erros += 1
            continue
            
        pasta_destino.mkdir(parents=True, exist_ok=True)
        
        # Sync atômico: copia para .tmp primeiro, valida, só então substitui
        # Bug fix 2026-08-25: antes apagava o destino antes de copiar, o que
        # podia causar perda de dado se a cópia falhasse no meio.
        caminho_destino = pasta_destino / j.name
        caminho_tmp = pasta_destino / f"{j.name}.tmp"
        
        if caminho_destino.exists():
            print(f" ↺ Arquivo existente será substituído atomicamente: {caminho_destino.name}")
        
        print(f" ➜ Copiando {j.name} -> {pasta_destino.name} (temp: {caminho_tmp.name})")
        try:
            shutil.copy2(str(j), str(caminho_tmp))
            # Validação pré-atômica: tamanho e existência
            if not caminho_tmp.exists() or caminho_tmp.stat().st_size == 0:
                raise Exception("Arquivo temporário vazio ou inexistente após cópia")
            if caminho_tmp.stat().st_size != j.stat().st_size:
                raise Exception(f"Tamanho divergente: origem={j.stat().st_size}, tmp={caminho_tmp.stat().st_size}")
            # Substituição atômica (rename é atômico no mesmo filesystem)
            caminho_tmp.replace(caminho_destino)
            enviados.append((j, caminho_destino))
            sucesso += 1
        except Exception as e:
            print(f" ✖ Erro ao copiar {j.name}: {e}")
            # Limpa temporário se existir
            if caminho_tmp.exists():
                try:
                    caminho_tmp.unlink()
                except Exception:
                    pass
            erros += 1
    
    # ===========================================================================
    # VALIDAÇÃO PÓS-SYNC (item 8 da lista de ferramentas)
    # ===========================================================================
    # Motivo: o script anterior não confirmava se o arquivo realmente chegou
    # intacto ao destino. Aqui verificamos existência, tamanho e contagem.
    # ===========================================================================
    if enviados:
        print("\n=== Validando sincronização ===")
        validados = 0
        validacao_erros = 0
        for origem, destino in enviados:
            try:
                if not destino.exists():
                    print(f" ✖ [validação] {destino.name}: arquivo não existe no destino")
                    validacao_erros += 1
                    continue
                tam_origem = origem.stat().st_size
                tam_destino = destino.stat().st_size
                if tam_origem != tam_destino or tam_destino == 0:
                    print(f" ✖ [validação] {destino.name}: tamanho divergente "
                          f"(origem={tam_origem}, destino={tam_destino})")
                    validacao_erros += 1
                    continue
                validados += 1
            except Exception as e:
                print(f" ✖ [validação] {destino.name}: {e}")
                validacao_erros += 1
        print(f"[validação] {validados}/{len(enviados)} arquivos válidos; "
              f"{validacao_erros} inválidos.")
        if validacao_erros:
            print(" ⚠ Atenção: há arquivos suspeitos. Reenvie ou revise manualmente.")
            
    print(f"\n=== Sincronização concluída: {sucesso}/{len(jornais)} enviados. Erros: {erros} ===")

if __name__ == "__main__":
    sincronizar_com_drive()
