#!/usr/bin/env python3
"""
Downloader de Boletins do TJRN - Notícias da Hora

Script para baixar automaticamente os boletins de áudio da página do TJRN.
Executar localmente no Brasil para evitar bloqueio por geolocalização.

Uso:
    python src/downloader_tjrn.py --data 2024-08-01 --saida ./boletins_brutos
    python src/downloader_tjrn.py --ultimos 5 --saida ./boletins_brutos
    python src/downloader_tjrn.py --todos --saida ./boletins_brutos
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ Dependências faltando: instale com 'pip install requests beautifulsoup4'")
    sys.exit(1)

from src.utils.logger import get_logger
from src.config.settings import Settings

logger = get_logger(__name__)

# Configurações
TJRN_BASE_URL = "https://tjrn.jus.br"
NOTICIAS_DA_HORA_URL = f"{TJRN_BASE_URL}/tjrnplay/programastv/noticias-da-hora/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


class TJRNDownloader:
    """Classe principal para download de boletins do TJRN."""

    def __init__(self, pasta_saida: str, timeout: int = 30, retry: int = 3):
        """
        Inicializa o downloader.

        Args:
            pasta_saida: Diretório base para salvar os boletins
            timeout: Timeout em segundos para requisições
            retry: Número de tentativas para downloads falhos
        """
        self.pasta_saida = Path(pasta_saida)
        self.timeout = timeout
        self.retry = retry
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

        # Criar pasta de saída se não existir
        self.pasta_saida.mkdir(parents=True, exist_ok=True)
        logger.info(f"Pasta de saída: {self.pasta_saida.absolute()}")

    def acessar_pagina(self, url: str) -> Optional[BeautifulSoup]:
        """
        Acessa uma página e retorna o BeautifulSoup parseado.

        Args:
            url: URL da página

        Returns:
            Objeto BeautifulSoup ou None se falhar
        """
        for tentativa in range(1, self.retry + 1):
            try:
                logger.debug(f"Tentativa {tentativa}/{self.retry}: {url}")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()

                # Verificar se foi bloqueado
                if "Acesso Bloqueado" in response.text:
                    logger.error("❌ Acesso bloqueado pelo TJRN. Execute este script dentro do Brasil.")
                    return None

                soup = BeautifulSoup(response.text, "html.parser")
                logger.debug(f"✅ Página acessada com sucesso ({len(response.text)} bytes)")
                return soup

            except requests.exceptions.RequestException as e:
                logger.warning(f"Tentativa {tentativa} falhou: {e}")
                if tentativa == self.retry:
                    logger.error(f"❌ Falha ao acessar {url} após {self.retry} tentativas")
                    return None

        return None

    def extrair_boletins(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extrai informações dos boletins da página.

        Args:
            soup: Objeto BeautifulSoup da página

        Returns:
            Lista de dicionários com dados dos boletins
        """
        boletins = []

        # Padrões comuns para encontrar players de áudio
        audio_tags = soup.find_all("audio")
        logger.info(f"Encontradas {len(audio_tags)} tags <audio> na página")

        for audio in audio_tags:
            audio_url = None

            # Tentar encontrar URL em diferentes formatos
            if audio.get("src"):
                audio_url = audio.get("src")
            elif audio.find("source"):
                source = audio.find("source")
                audio_url = source.get("src")

            if not audio_url:
                continue

            # Completar URL relativa
            audio_url = urljoin(TJRN_BASE_URL, audio_url)

            # Extrair data e número do boletim do contexto
            parent = audio.find_parent(["div", "article", "section"])
            texto_contexto = parent.get_text(strip=True) if parent else ""

            # Tentar extrair data do texto
            data_boletim = self._extrair_data(texto_contexto)
            if not data_boletim:
                data_boletim = datetime.now().strftime("%Y-%m-%d")

            # Tentar extrair número do boletim (B1, B2, etc.)
            num_boletim = self._extrair_numero_boletim(texto_contexto)

            # Extrair título/descrição
            titulo = self._extrair_titulo(parent)

            boletim = {
                "url": audio_url,
                "data": data_boletim,
                "numero": num_boletim,
                "titulo": titulo,
                "nome_arquivo": self._gerar_nome_arquivo(data_boletim, num_boletim),
            }

            boletins.append(boletim)
            logger.debug(f"Boletim encontrado: {boletim['nome_arquivo']}")

        # Se não encontrou tags <audio>, tentar encontrar links diretos
        if not boletins:
            logger.info("Nenhuma tag <audio> encontrada. Buscando links diretos...")
            boletins = self._extrair_links_diretos(soup)

        logger.info(f"Total de boletins extraídos: {len(boletins)}")
        return boletins

    def _extrair_data(self, texto: str) -> Optional[str]:
        """Extrai data do texto no formato DD/MM/YYYY ou similar."""
        padroes_data = [
            r"(\d{1,2})/(\d{1,2})/(\d{4})",  # DD/MM/YYYY
            r"(\d{4})-(\d{2})-(\d{2})",  # YYYY-MM-DD
            r"(\d{1,2}) de (\w+) de (\d{4})",  # DD de Mês de YYYY
        ]

        for padrao in padroes_data:
            match = re.search(padrao, texto, re.IGNORECASE)
            if match:
                try:
                    if len(match.groups()) == 3:
                        if padrao.count("YYYY") > 0 or padrao.count("YYYY") > 0:
                            dia, mes, ano = match.groups()
                            meses = {
                                "janeiro": "01", "fevereiro": "02", "março": "03",
                                "abril": "04", "maio": "05", "junho": "06",
                                "julho": "07", "agosto": "08", "setembro": "09",
                                "outubro": "10", "novembro": "11", "dezembro": "12",
                            }
                            if mes.lower() in meses:
                                mes = meses[mes.lower()]
                            return f"{ano}-{int(mes):02d}-{int(dia):02d}"
                        else:
                            ano, mes, dia = match.groups()
                            return f"{ano}-{mes}-{dia}"
                except Exception:
                    continue
        return None

    def _extrair_numero_boletim(self, texto: str) -> Optional[int]:
        """Extrai número do boletim (B1, B2, etc.)."""
        padrao = r"[Bb](?:oletim)?[\s\.]?(\d+)"
        match = re.search(padrao, texto)
        if match:
            return int(match.group(1))
        return None

    def _extrair_titulo(self, elemento) -> str:
        """Extrai título do boletim."""
        if not elemento:
            return "Boletim sem título"

        # Tentar encontrar em h1, h2, h3, ou classe de título
        for tag in ["h1", "h2", "h3", "h4"]:
            titulo_tag = elemento.find(tag)
            if titulo_tag:
                return titulo_tag.get_text(strip=True)

        # Tentar por classe
        classes_comuns = ["title", "titulo", "headline", "nome"]
        for classe in classes_comuns:
            titulo_tag = elemento.find(class_=lambda c: c and classe.lower() in c.lower())
            if titulo_tag:
                return titulo_tag.get_text(strip=True)

        return "Boletim de Notícias"

    def _extrair_links_diretos(self, soup: BeautifulSoup) -> List[Dict]:
        """Extrai links diretos de arquivos de áudio quando não há tags <audio>."""
        boletins = []

        # Buscar links para arquivos .mp3, .wav, .m4a
        extensoes_audio = [".mp3", ".wav", ".m4a", ".aac", ".ogg"]
        links = soup.find_all("a", href=True)

        for link in links:
            href = link.get("href", "")
            if any(href.lower().endswith(ext) for ext in extensoes_audio):
                audio_url = urljoin(TJRN_BASE_URL, href)

                # Tentar extrair metadados do texto do link ou contexto
                texto_link = link.get_text(strip=True)
                data_boletim = self._extrair_data(texto_link) or datetime.now().strftime("%Y-%m-%d")
                num_boletim = self._extrair_numero_boletim(texto_link)

                boletim = {
                    "url": audio_url,
                    "data": data_boletim,
                    "numero": num_boletim,
                    "titulo": texto_link or "Boletim",
                    "nome_arquivo": self._gerar_nome_arquivo(data_boletim, num_boletim),
                }

                boletins.append(boletim)

        return boletins

    def _gerar_nome_arquivo(self, data: str, numero: Optional[int]) -> str:
        """Gera nome do arquivo no padrão esperado pelo pipeline."""
        if numero:
            return f"B{numero}_{data}.mp3"
        else:
            # Se não tem número, usar timestamp
            timestamp = datetime.now().strftime("%H%M%S")
            return f"B_{data}_{timestamp}.mp3"

    def baixar_boletim(self, boletim: Dict, pasta_data: Path) -> Optional[Path]:
        """
        Baixa um único boletim.

        Args:
            boletim: Dicionário com dados do boletim
            pasta_data: Pasta específica para esta data

        Returns:
            Caminho do arquivo baixado ou None se falhar
        """
        url = boletim["url"]
        nome_arquivo = boletim["nome_arquivo"]
        caminho_destino = pasta_data / nome_arquivo

        # Verificar se já existe
        if caminho_destino.exists():
            logger.info(f"⏭️  Arquivo já existe: {caminho_destino}")
            return caminho_destino

        logger.info(f"📥 Baixando: {nome_arquivo}")

        for tentativa in range(1, self.retry + 1):
            try:
                response = self.session.get(url, timeout=self.timeout, stream=True)
                response.raise_for_status()

                # Escrever arquivo
                with open(caminho_destino, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                tamanho = caminho_destino.stat().st_size
                logger.info(f"✅ Download concluído: {nome_arquivo} ({tamanho / 1024:.1f} KB)")
                return caminho_destino

            except requests.exceptions.RequestException as e:
                logger.warning(f"Tentativa {tentativa} falhou: {e}")
                if tentativa == self.retry:
                    logger.error(f"❌ Falha ao baixar {nome_arquivo}")
                    return None

        return None

    def baixar_todos(self, boletins: List[Dict]) -> Dict[str, List[Path]]:
        """
        Baixa todos os boletins organizados por data.

        Args:
            boletins: Lista de dicionários com dados dos boletins

        Returns:
            Dicionário {data: [caminhos_dos_arquivos]}
        """
        resultados = {}

        for boletim in boletins:
            data = boletim["data"]
            pasta_data = self.pasta_saida / data
            pasta_data.mkdir(parents=True, exist_ok=True)

            caminho = self.baixar_boletim(boletim, pasta_data)
            if caminho:
                if data not in resultados:
                    resultados[data] = []
                resultados[data].append(caminho)

        # Ordenar boletins por número dentro de cada data
        for data in resultados:
            resultados[data].sort(key=lambda p: p.name)

        return resultados

    def executar(
        self,
        data_especifica: Optional[str] = None,
        ultimos_dias: Optional[int] = None,
        todos: bool = False,
    ) -> Dict[str, List[Path]]:
        """
        Executa o download conforme critérios especificados.

        Args:
            data_especifica: Data específica no formato YYYY-MM-DD
            ultimos_dias: Número de dias para baixar (contando de hoje)
            todos: Baixar todos os boletins disponíveis

        Returns:
            Dicionário {data: [caminhos_dos_arquivos]}
        """
        logger.info("🚀 Iniciando download de boletins do TJRN")

        # Acessar página principal
        soup = self.acessar_pagina(NOTICIAS_DA_HORA_URL)
        if not soup:
            logger.error("❌ Falha ao acessar página do TJRN")
            return {}

        # Extrair boletins
        boletins = self.extrair_boletins(soup)
        if not boletins:
            logger.warning("⚠️  Nenhum boletim encontrado na página")
            return {}

        # Filtrar conforme critério
        boletins_filtrados = self._filtrar_boletins(
            boletins, data_especifica, ultimos_dias, todos
        )

        logger.info(f"📋 Boletins para download: {len(boletins_filtrados)}")

        # Baixar
        resultados = self.baixar_todos(boletins_filtrados)

        # Resumo
        total_baixados = sum(len(arqs) for arqs in resultados.values())
        logger.info(f"✅ Download concluído: {total_baixados} boletins em {len(resultados)} datas")

        return resultados

    def _filtrar_boletins(
        self,
        boletins: List[Dict],
        data_especifica: Optional[str],
        ultimos_dias: Optional[int],
        todos: bool,
    ) -> List[Dict]:
        """Filtra boletins conforme critérios."""
        if data_especifica:
            return [b for b in boletins if b["data"] == data_especifica]

        if ultimos_dias:
            data_limite = (datetime.now() - timedelta(days=ultimos_dias)).strftime("%Y-%m-%d")
            return [b for b in boletins if b["data"] >= data_limite]

        if todos:
            return boletins

        # Default: últimos 7 dias
        data_limite = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        return [b for b in boletins if b["data"] >= data_limite]


def main():
    """Função principal com CLI."""
    parser = argparse.ArgumentParser(
        description="Baixar boletins de áudio do TJRN - Notícias da Hora",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s --data 2024-08-01 --saida ./boletins_brutos
  %(prog)s --ultimos 5 --saida ./boletins_brutos
  %(prog)s --todos --saida ./boletins_brutos
  %(prog)s --dry-run  # Simula sem baixar
        """,
    )

    parser.add_argument(
        "--data",
        type=str,
        help="Data específica no formato YYYY-MM-DD",
    )
    parser.add_argument(
        "--ultimos",
        type=int,
        help="Número de dias para baixar (contando de hoje)",
    )
    parser.add_argument(
        "--todos",
        action="store_true",
        help="Baixar todos os boletins disponíveis",
    )
    parser.add_argument(
        "--saida",
        type=str,
        default="./boletins_brutos",
        help="Pasta de saída (padrão: ./boletins_brutos)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout em segundos (padrão: 30)",
    )
    parser.add_argument(
        "--retry",
        type=int,
        default=3,
        help="Número de tentativas (padrão: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular execução sem baixar arquivos",
    )

    args = parser.parse_args()

    # Validar argumentos
    if not any([args.data, args.ultimos, args.todos]):
        parser.error("É necessário especificar --data, --ultimos ou --todos")

    if args.dry_run:
        logger.info("🔍 MODO DRY-RUN: Nenhuma operação será realizada")

    # Executar
    try:
        downloader = TJRNDownloader(
            pasta_saida=args.saida,
            timeout=args.timeout,
            retry=args.retry,
        )

        if args.dry_run:
            # Apenas listar o que seria baixado
            soup = downloader.acessar_pagina(NOTICIAS_DA_HORA_URL)
            if soup:
                boletins = downloader.extrair_boletins(soup)
                boletins_filtrados = downloader._filtrar_boletins(
                    boletins, args.data, args.ultimos, args.todos
                )
                logger.info(f"📋 Boletins que seriam baixados: {len(boletins_filtrados)}")
                for b in boletins_filtrados:
                    logger.info(f"  - {b['nome_arquivo']} ({b['url']})")
            return 0

        resultados = downloader.executar(
            data_especifica=args.data,
            ultimos_dias=args.ultimos,
            todos=args.todos,
        )

        if not resultados:
            logger.warning("⚠️  Nenhum boletim foi baixado")
            return 1

        # Imprimir resumo
        print("\n" + "=" * 60)
        print("📊 RESUMO DO DOWNLOAD")
        print("=" * 60)
        for data, arquivos in sorted(resultados.items()):
            print(f"\n{data}: {len(arquivos)} boletim(s)")
            for arq in arquivos:
                tamanho_kb = arq.stat().st_size / 1024
                print(f"  ✅ {arq.name} ({tamanho_kb:.1f} KB)")

        print("\n✅ Processo concluído com sucesso!")
        return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Processo interrompido pelo usuário")
        return 130
    except Exception as e:
        logger.exception(f"❌ Erro inesperado: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
