#!/usr/bin/env python3
"""
Saneamento e Organização de Jornais no Drive

Organiza arquivos de jornais em pastas mensais, resolve duplicatas,
gerencia fins de semana e gera quarentena para itens problemáticos.

Uso:
    python src/sanear_drive.py --origem data/output/JORNAIS_FINAL --destino "H:/Meu Drive/.../03_AUDIOS_RADIO"
"""

import argparse
import csv
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Mapeamento de meses
MESES_MAP = {
    '01': 'JAN', '02': 'FEV', '03': 'MAR', '04': 'ABR',
    '05': 'MAI', '06': 'JUN', '07': 'JUL', '08': 'AGO',
    '09': 'SET', '10': 'OUT', '11': 'NOV', '12': 'DEZ'
}


class SaneadorDrive:
    """Classe principal para saneamento de jornais no Drive."""

    def __init__(self, origem: str, destino: str):
        """
        Inicializa o saneador.

        Args:
            origem: Pasta com arquivos brutos a organizar
            destino: Pasta de destino final (03_AUDIOS_RADIO)
        """
        self.origem = Path(origem)
        self.destino = Path(destino)
        self.quarentena = self.destino.parent / "00_QUARENTENA"
        self.manifesto_path = self.quarentena / "manifesto.csv"
        
        # Criar pastas necessárias
        self.destino.mkdir(parents=True, exist_ok=True)
        self.quarentena.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📁 Origem: {self.origem}")
        logger.info(f"📁 Destino: {self.destino}")
        logger.info(f"📁 Quarentena: {self.quarentena}")

    def extrair_metadados(self, nome_arquivo: str) -> Optional[Dict]:
        """Extrai NJUD e data do nome do arquivo."""
        # Padrão: NJUD_XXXX_DD-MM-AAAA.mp3 ou NJUD_XXXX_DD-MM-AAAA_INCOMPLETO.mp3
        padrao = r"NJUD_(\d+)_(\d{2})-(\d{2})-(\d{4})(?:_INCOMPLETO)?\.mp3"
        match = re.match(padrao, nome_arquivo)
        
        if not match:
            return None
        
        njud = int(match.group(1))
        dia, mes, ano = match.group(2), match.group(3), match.group(4)
        data_str = f"{ano}-{mes}-{dia}"
        incompleto = "_INCOMPLETO" in nome_arquivo
        
        try:
            dt = datetime.strptime(data_str, "%Y-%m-%d")
            weekday = dt.weekday()  # 0=Segunda, 6=Domingo
            eh_fim_de_semana = weekday >= 5
        except ValueError:
            return None
        
        return {
            'nome': nome_arquivo,
            'njud': njud,
            'data': data_str,
            'dia': dia,
            'mes': mes,
            'ano': ano,
            'incompleto': incompleto,
            'eh_fim_de_semana': eh_fim_de_semana,
            'weekday': weekday
        }

    def coletar_arquivos(self) -> List[Dict]:
        """Coleta todos os arquivos MP3 da pasta de origem."""
        arquivos = []
        
        for mp3_file in self.origem.glob("*.mp3"):
            metadados = self.extrair_metadados(mp3_file.name)
            if metadados:
                metadados['caminho'] = mp3_file
                arquivos.append(metadados)
        
        logger.info(f"📋 Coletados {len(arquivos)} arquivos válidos")
        return arquivos

    def resolver_fim_de_semana(self, arquivos: List[Dict]) -> List[Dict]:
        """Realoca arquivos de fim de semana para segunda-feira."""
        for arq in arquivos:
            if arq['eh_fim_de_semana']:
                # Calcular próxima segunda-feira
                dt_original = datetime.strptime(arq['data'], "%Y-%m-%d")
                dias_para_segunda = 7 - arq['weekday'] if arq['weekday'] == 6 else 1
                dt_segunda = dt_original + timedelta(days=dias_para_segunda)
                
                arq['data_realocada'] = dt_segunda.strftime("%Y-%m-%d")
                arq['motivo_realocacao'] = f"Fim de semana ({dt_original.strftime('%d/%m/%Y')})"
                logger.debug(f"📅 {arq['nome']} realocado de {arq['data']} para {arq['data_realocada']}")
        
        return arquivos

    def deduplicar(self, arquivos: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Remove duplicatas, mantendo o melhor arquivo por data.
        Retorna (arquivos_mantidos, arquivos_quarentena).
        """
        # Agrupar por data (considerando realocação se existir)
        por_data = defaultdict(list)
        for arq in arquivos:
            data_chave = arq.get('data_realocada', arq['data'])
            por_data[data_chave].append(arq)
        
        mantidos = []
        quarentena = []
        
        for data, grupo in por_data.items():
            if len(grupo) == 1:
                mantidos.append(grupo[0])
            else:
                # Ordenar: completos primeiro, depois NJUD maior
                grupo_ordenado = sorted(
                    grupo,
                    key=lambda x: (x['incompleto'], -x['njud'])
                )
                
                # Manter o primeiro (melhor)
                mantidos.append(grupo_ordenado[0])
                
                # Os demais vão para quarentena
                for arq in grupo_ordenado[1:]:
                    arq['motivo_quarentena'] = f"Duplicata em {data} (mantido NJUD {grupo_ordenado[0]['njud']})"
                    quarentena.append(arq)
        
        logger.info(f"✅ Mantidos {len(mantidos)} arquivos únicos")
        logger.info(f"⚠️  Quarentena: {len(quarentena)} duplicatas")
        
        return mantidos, quarentena

    def mover_para_pastas_mensais(self, arquivos: List[Dict]) -> Dict[str, int]:
        """Move arquivos para pastas mensais no destino."""
        estatisticas = defaultdict(int)
        
        for arq in arquivos:
            mes_num = arq['mes']
            mes_nome = MESES_MAP.get(mes_num, f"MES_{mes_num}")
            ano = arq['ano']
            
            # Nome da pasta: "MM - MES - AA"
            nome_pasta = f"{mes_num} - {mes_nome} - {ano[-2:]}"
            pasta_destino = self.destino / nome_pasta
            pasta_destino.mkdir(parents=True, exist_ok=True)
            
            # Copiar arquivo
            caminho_destino = pasta_destino / arq['nome']
            shutil.copy2(arq['caminho'], caminho_destino)
            estatisticas[nome_pasta] += 1
        
        return dict(estatisticas)

    def mover_para_quarentena(self, arquivos: List[Dict], motivo_padrao: str = ""):
        """Move arquivos para quarentena e registra no manifesto."""
        registros_manifesto = []
        
        for arq in arquivos:
            motivo = arq.get('motivo_quarentena', arq.get('motivo_realocacao', motivo_padrao))
            destino_quarentena = self.quarentena / arq['nome']
            
            # Evitar sobrescrever na quarentena
            contador = 1
            while destino_quarentena.exists():
                stem = arq['nome'].replace('.mp3', '')
                destino_quarentena = self.quarentena / f"{stem}_v{contador}.mp3"
                contador += 1
            
            shutil.copy2(arq['caminho'], destino_quarentena)
            
            registros_manifesto.append({
                'arquivo_original': arq['nome'],
                'njud': arq['njud'],
                'data': arq['data'],
                'motivo': motivo,
                'data_processamento': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Atualizar manifesto
        self._salvar_manifesto(registros_manifesto)
        logger.info(f"📦 Movidos {len(arquivos)} arquivos para quarentena")

    def _salvar_manifesto(self, registros: List[Dict]):
        """Salva ou atualiza o manifesto CSV."""
        arquivo_existe = self.manifesto_path.exists()
        
        with open(self.manifesto_path, 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['arquivo_original', 'njud', 'data', 'motivo', 'data_processamento']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not arquivo_existe:
                writer.writeheader()
            
            writer.writerows(registros)

    def executar(self) -> Dict:
        """Executa todo o processo de saneamento."""
        logger.info("🚀 Iniciando saneamento...")
        
        # 1. Coletar arquivos
        arquivos = self.coletar_arquivos()
        if not arquivos:
            logger.warning("⚠️  Nenhum arquivo encontrado para processar")
            return {'sucesso': False, 'mensagem': 'Nenhum arquivo encontrado'}
        
        # 2. Resolver fins de semana
        arquivos = self.resolver_fim_de_semana(arquivos)
        
        # 3. Deduplicar
        mantidos, quarentena = self.deduplicar(arquivos)
        
        # 4. Mover quarentena primeiro
        if quarentena:
            self.mover_para_quarentena(quarentena)
        
        # 5. Mover mantidos para pastas mensais
        estatisticas = self.mover_para_pastas_mensais(mantidos)
        
        # 6. Relatório final
        total_moved = sum(estatisticas.values())
        logger.info("=" * 60)
        logger.info("✅ SANEAMENTO CONCLUÍDO")
        logger.info("=" * 60)
        logger.info(f"📊 Total processado: {len(arquivos)} arquivos")
        logger.info(f"✅ Organizados: {total_moved} arquivos")
        logger.info(f"⚠️  Quarentena: {len(quarentena)} arquivos")
        logger.info("\nDistribuição por mês:")
        for pasta, qtd in sorted(estatisticas.items()):
            logger.info(f"  📁 {pasta}: {qtd} arquivos")
        
        return {
            'sucesso': True,
            'total_processado': len(arquivos),
            'organizados': total_moved,
            'quarentena': len(quarentena),
            'por_mes': estatisticas
        }


def main():
    parser = argparse.ArgumentParser(
        description="Saneamento e organização de jornais no Drive"
    )
    parser.add_argument(
        "--origem",
        type=str,
        default="data/output/JORNAIS_FINAL",
        help="Pasta com arquivos brutos (padrão: data/output/JORNAIS_FINAL)"
    )
    parser.add_argument(
        "--destino",
        type=str,
        required=True,
        help="Pasta de destino final (03_AUDIOS_RADIO)"
    )
    
    args = parser.parse_args()
    
    try:
        saneador = SaneadorDrive(args.origem, args.destino)
        resultado = saneador.executar()
        
        return 0 if resultado['sucesso'] else 1
    
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Processo interrompido pelo usuário")
        return 130
    except Exception as e:
        logger.exception(f"❌ Erro inesperado: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
