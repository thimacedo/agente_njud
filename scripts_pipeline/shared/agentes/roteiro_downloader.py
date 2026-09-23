#!/usr/bin/env python3
"""
AgenteRoteiroDownloader — Baixa roteiros do Google Docs e salva como TXT.

Integra com o pipeline DIVISOR: docs do Google Docs → pasta de roteiros.
Suporta dois modos:
  1. Lista de links (colados via CLI ou arquivo)
  2. Pasta compartilhada do Google Drive (via gdown/api — futuro)

Uso:
  python -m shared.agentes.roteiro_downloader --links "url1 url2 ..." --saida ./roteiros/
  python -m shared.agentes.roteiro_downloader --arquivo links.txt --saida ./roteiros/
  python -m shared.agentes.roteiro_downloader --interactive
"""

import argparse
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# Adicionar scripts_pipeline ao path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts_pipeline"))

from shared.logging_config import get_logger

logger = get_logger("roteiro_downloader")

# Regex para extrair ID do Google Docs
REGEX_DOC_ID = r'/d/([a-zA-Z0-9-_]+)'
# Regex para datas DD/MM/AAAA ou DD_MM_AAAA ou DD/MM/AA
# Usa lookbehind/lookahead com [^a-zA-Z0-9] (não \w, pois _ é word char)
REGEX_DATA = r'(?:^|(?<=[^a-zA-Z0-9]))(0[1-9]|[12][0-9]|3[01])[/_](0[1-9]|1[0-12])[/_](\d{2,4})(?=[^a-zA-Z0-9]|$)'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}


def extrair_ids(texto: str) -> list[str]:
    """Extrai IDs únicos de links do Google Docs, preservando ordem."""
    ids = []
    for match in re.findall(REGEX_DOC_ID, texto):
        if match not in ids:
            ids.append(match)
    return ids


def extrair_datas(texto: str) -> list[datetime]:
    """Extrai datas DD/MM/AAAA, DD_MM_AAAA ou DD/MM/AA do texto."""
    datas = []
    for dia, mes, ano in re.findall(REGEX_DATA, texto):
        try:
            ano_int = int(ano)
            # Anos de 2 dígitos: 26 -> 2026, 99 -> 1999
            if ano_int < 100:
                ano_int += 2000 if ano_int < 50 else 1900
            datas.append(datetime(ano_int, int(mes), int(dia)))
        except ValueError:
            continue
    return datas


def extrair_metadados_roteiro(texto: str) -> dict:
    """
    Extrai metadados estruturados do roteiro.
    Retorna dict com: boletins (list de dict), data_marcada
    """
    boletins = []
    
    # Split por marcadores de boletim (B{número}- ou B{número} —)
    # Usar lookahead para não consumir o delimitador
    blocos = re.split(r'(?=^B\d{1,2}\s*[-–—])', texto, flags=re.MULTILINE)
    
    for bloco in blocos:
        bloco = bloco.strip()
        if not bloco:
            continue
        
        # Procurar padrão B{N}- TITULO no início do bloco
        m_b = re.match(r'B(\d{1,2})\s*[-–—]\s*(.+?)(?:\n|$)', bloco, re.I)
        if not m_b:
            continue
        
        numero = int(m_b.group(1))
        titulo = m_b.group(2).strip()
        cabeca = ""
        off = ""
        
        m_cab = re.search(r'CABEÇA:\s*(.+?)(?:\n\n|\nOFF:|\n*$)', bloco, re.I | re.DOTALL)
        if m_cab:
            cabeca = m_cab.group(1).strip()
        
        m_off = re.search(r'OFF:\s*(.+?)(?:\n\n|\nB\d|$)', bloco, re.I | re.DOTALL)
        if m_off:
            off = m_off.group(1).strip()
        
        boletins.append({
            "numero": numero,
            "titulo": titulo,
            "cabeca": cabeca,
            "off": off
        })
    
    # Extrair datas
    datas = extrair_datas(texto)
    data_marcada = max(datas) if datas else None
    
    return {
        "boletins": boletins,
        "data": data_marcada
    }


def baixar_doc(doc_id: str, timeout: int = 30) -> str:
    """
    Baixa um Google Doc como TXT via URL de exportação.
    Retorna o conteúdo em texto (BOM removido).
    
    Raises:
        Exception: se falhar após retries
    """
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    max_retries = 3
    
    for tentativa in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(export_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                conteudo = response.read().decode('utf-8-sig')  # Remove BOM automaticamente
                return conteudo.strip()
        except Exception as e:
            if tentativa < max_retries:
                logger.warning(f"Tentativa {tentativa}/{max_retries} falhou para {doc_id}: {e}. Retrying...")
                time.sleep(2 ** tentativa)  # Exponential backoff
            else:
                raise Exception(f"Falha ao baixar {doc_id} após {max_retries} tentativas: {e}")


def salvar_roteiro_unificado(documentos: list[dict], pasta_saida: Path) -> Path:
    """
    Salva roteiros baixados como arquivo TXT unificado.
    
    Formato compatível com carregar_roteiros() do pipeline:
    - Separadores entre documentos
    - B{N}- TITULO
    - CABEÇA: ...
    - OFF: ...
    """
    # Determinar nome do arquivo
    todas_datas = []
    for doc in documentos:
        datas = extrair_datas(doc["conteudo"])
        todas_datas.extend(datas)
    
    if todas_datas:
        data_str = max(todas_datas).strftime("%Y-%m-%d")
    else:
        data_str = datetime.now().strftime("%Y-%m-%d")
    
    pasta_saida.mkdir(parents=True, exist_ok=True)
    nome_arquivo = pasta_saida / f"roteiros_{data_str}.txt"
    
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        for i, doc in enumerate(documentos, 1):
            if doc["status"] == "ERRO":
                f.write("=" * 50 + "\n")
                f.write(f"DOCUMENTO [{i}/{len(documentos)}] - ERRO\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"[ERRO AO EXTRAR DOCUMENTO ID: {doc['id']}]\n\n\n")
            else:
                f.write("=" * 50 + "\n")
                f.write(f"DOCUMENTO [{i}/{len(documentos)}] - ID: {doc['id']}\n")
                f.write("=" * 50 + "\n\n")
                f.write(doc["conteudo"] + "\n\n\n")
    
    logger.info(f"Roteiros salvos em: {nome_arquivo}")
    return nome_arquivo


def salvar_roteiros_individuais(documentos: list[dict], pasta_saida: Path) -> list[Path]:
    """
    Salva cada roteiro como arquivo individual, organizado por boletim.
    Útil quando cada doc contém um boletim específico.
    """
    paths = []
    
    for doc in documentos:
        if doc["status"] == "ERRO":
            continue
        
        meta = extrair_metadados_roteiro(doc["conteudo"])
        
        for b in meta["boletins"]:
            pasta_saida.mkdir(parents=True, exist_ok=True)
            nome = f"B{b['numero']}- {b['titulo']}.txt"
            # Sanitizar nome
            nome = re.sub(r'[<>:"/\\|?*]', '_', nome)
            path = pasta_saida / nome
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"B{b['numero']}- {b['titulo']}\n")
                if b['cabeca']:
                    f.write(f"CABEÇA: {b['cabeca']}\n")
                if b['off']:
                    f.write(f"OFF: {b['off']}\n")
            
            paths.append(path)
            logger.debug(f"Roteiro individual salvo: {path.name}")
    
    return paths


def processar_links(links_texto: str, pasta_saida: Path, modo: str = "unificado") -> dict:
    """
    Pipeline completo: links → download → salvamento.
    
    Args:
        links_texto: Texto contendo links do Google Docs
        pasta_saida: Pasta onde salvar os TXTs
        modo: "unificado" (arquivo único) ou "individual" (um arquivo por boletim)
    
    Returns:
        dict com status, arquivos_criados, erros, estatisticas
    """
    ids = extrair_ids(links_texto)
    
    if not ids:
        logger.error("Nenhum link válido do Google Docs encontrado.")
        return {
            "status": "erro",
            "mensagem": "Nenhum link válido encontrado",
            "arquivos_criados": [],
            "erros": ["Nenhum link válido do Google Docs"],
            "estatisticas": {"total": 0, "sucesso": 0, "falha": 0}
        }
    
    logger.info(f"Encontrados {len(ids)} documentos únicos para baixar.")
    
    documentos = []
    erros = []
    
    for i, doc_id in enumerate(ids, 1):
        logger.info(f"[{i}/{len(ids)}] Baixando: {doc_id}")
        
        try:
            conteudo = baixar_doc(doc_id)
            documentos.append({
                "id": doc_id,
                "status": "OK",
                "conteudo": conteudo
            })
            logger.info(f"  ✅ {len(conteudo)} caracteres baixados")
        except Exception as e:
            logger.error(f"  ❌ Falha: {e}")
            documentos.append({
                "id": doc_id,
                "status": "ERRO",
                "conteudo": ""
            })
            erros.append(f"{doc_id}: {e}")
    
    # Salvar
    arquivos_criados = []
    
    if modo == "unificado":
        path = salvar_roteiro_unificado(documentos, pasta_saida)
        arquivos_criados.append(str(path))
    elif modo == "individual":
        paths = salvar_roteiros_individuais(documentos, pasta_saida)
        arquivos_criados = [str(p) for p in paths]
    
    sucesso = sum(1 for d in documentos if d["status"] == "OK")
    
    resultado = {
        "status": "sucesso" if sucesso == len(ids) else "parcial" if sucesso > 0 else "erro",
        "arquivos_criados": arquivos_criados,
        "erros": erros,
        "estatisticas": {
            "total": len(ids),
            "sucesso": sucesso,
            "falha": len(ids) - sucesso
        }
    }
    
    logger.info(f"Concluído: {sucesso}/{len(ids)} documentos baixados com sucesso.")
    return resultado


def main():
    parser = argparse.ArgumentParser(
        description="Baixa roteiros do Google Docs e salva como TXT"
    )
    parser.add_argument(
        "--links", "-l",
        help="Links do Google Docs (separados por espaço ou quebra de linha)",
        default=None
    )
    parser.add_argument(
        "--arquivo", "-a",
        help="Arquivo contendo links (um por linha)",
        default=None
    )
    parser.add_argument(
        "--saida", "-s",
        help="Pasta de saída (default: ./roteiros/)",
        default="./roteiros/"
    )
    parser.add_argument(
        "--modo", "-m",
        choices=["unificado", "individual"],
        default="unificado",
        help="Modo de salvamento (default: unificado)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Modo interativo (colar links via stdin)"
    )
    
    args = parser.parse_args()
    
    # Determinar fonte dos links
    if args.interactive or (not args.links and not args.arquivo):
        print("=" * 60)
        print("📄 ROTEIRO DOWNLOADER — Google Docs → TXT")
        print("=" * 60)
        print("Cole os links abaixo (ENTER em linha vazia para processar):\n")
        
        linhas = []
        while True:
            try:
                linha = input()
                if not linha.strip() and len(linhas) > 0:
                    break
                if linha.strip():
                    linhas.append(linha)
            except EOFError:
                break
        
        links_texto = " ".join(linhas)
    
    elif args.arquivo:
        path = Path(args.arquivo)
        if not path.exists():
            logger.error(f"Arquivo não encontrado: {path}")
            sys.exit(1)
        links_texto = path.read_text(encoding="utf-8")
    
    else:
        links_texto = args.links
    
    pasta_saida = Path(args.saida)
    
    resultado = processar_links(links_texto, pasta_saida, args.modo)
    
    print(f"\n{'='*60}")
    print(f"Resultado: {resultado['status'].upper()}")
    print(f"  Total: {resultado['estatisticas']['total']}")
    print(f"  Sucesso: {resultado['estatisticas']['sucesso']}")
    print(f"  Falha: {resultado['estatisticas']['falha']}")
    
    if resultado['arquivos_criados']:
        print(f"\n  Arquivos:")
        for arq in resultado['arquivos_criados']:
            print(f"    📄 {arq}")
    
    if resultado['erros']:
        print(f"\n  Erros:")
        for erro in resultado['erros']:
            print(f"    ⚠️ {erro}")
    
    # Exit code baseado no resultado
    if resultado['status'] == 'erro':
        sys.exit(1)


if __name__ == "__main__":
    main()
