#!/usr/bin/env python3
"""
Pipeline canônico de edição de boletins — processar_boletim_canonico.py
Uso: processar_boletim_canonico.py <arquivo_entrada> [--roteiros <pasta_roteiros>]
Saída: pasta <arquivo_entrada>_saida/ com boletins editados + auditoria.json

Refatorado: funções extraídas para módulos em etapas/.
"""
import argparse, re, os, json, sys, tempfile
from pathlib import Path
from datetime import date
from pydub import AudioSegment

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))  # adiciona scripts_pipeline/ao path

from corrigir_alucinacoes import corrigir_transcricao
from shared.text_utils import normalizar_texto
from shared.logging_config import setup_logging, get_logger

# Importar etapas modularizadas
from etapas.etapa_triagem import triagem_audio, carregar_modelo
from etapas.etapa_transcricao import transcrever
from etapas.etapa_estrutura import (
    detectar_estrutura,
    detectar_repeticoes_confirmadas,
    detectar_claquete_geral,
    detectar_claquetes_por_assinatura
)
from etapas.etapa_cortes import processar_cortes_boletim
from etapas.etapa_montagem import montar_boletim_com_vinhetas, calcular_duracao_cabeca

# ── Configuração (todas as variáveis antes hardcoded) ─────────────────────────
# Overrides via variáveis de ambiente (opcional): DIVISOR_ASSETS, DIVISOR_TMP,
# DIVISOR_WHISPER_MODEL, DIVISOR_COBERTURA_MIN.
# Defaults derivados da localização deste script — funciona em qualquer checkout.

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VHT_DIR = Path(os.environ.get("DIVISOR_ASSETS", PROJECT_ROOT / "assets" / "vinhetas" / "boletim"))
TMP_DIR = Path(os.environ.get("DIVISOR_TMP", tempfile.gettempdir()))
BG_PATH = VHT_DIR / "BG - BOLETIM.mp3"

WHISPER_MODEL = os.environ.get("DIVISOR_WHISPER_MODEL", "small")
COBERTURA_MIN = float(os.environ.get("DIVISOR_COBERTURA_MIN", "0.6"))  # Item 18: 60% + auditoria humana

# Fallbacks de data quando o filename não traz mês/ano explícitos
MES_PADRAO = "09"   # arquivos "DD SET" → setembro
ANO_PADRAO = "2026" # projeto DIVISOR 2026


def nomear_boletim(data_str, numero, roteiro_texto=None, data_completa_str=None):
    """Gera nome canônico BOLETIM_RADIO_TJRN_DD_MM_AAAA_B{N}__TITULO.mp3
    
    data_completa_str: string DD_MM_AAAA (ex: "04_09_2026"). 
    Se None, tenta extrair do data_str (ex: "04 SET" -> dia 04) e usa 2026 como padrão.
    """
    dd, mm, aaaa = "??", "??", "????"
    
    if data_completa_str:
        partes = data_completa_str.split("_")
        if len(partes) == 3:
            dd, mm, aaaa = partes[0], partes[1], partes[2]
        else:
            dd, mm, aaaa = "??", "??", "????"
    else:
        # Extrair dia do data_str (ex: "04 SET" -> dia 04)
        m_data = re.search(r'(\d{1,2})\s*[Ss][Ee][Tt]', data_str or "", re.I)
        if m_data:
            dd = m_data.group(1).zfill(2)
            mm = MES_PADRAO
            aaaa = ANO_PADRAO
        else:
            dd, mm, aaaa = "??", "??", "????"
    
    # Extrair título do roteiro se disponível
    titulo = ""
    if roteiro_texto:
        # Tenta formato "B{N}- TITULO"
        m_ret = re.search(rf'B{numero}\s*[-–]\s*(.+?)(?:\n|$)', roteiro_texto, re.I)
        if m_ret:
            titulo = m_ret.group(1).strip()
        else:
            # Tenta formato só "TITULO" (já extraído pelo carregar_roteiros)
            # Remove prefixos como "B{N}-" ou "B{N} " se existirem
            limpo = re.sub(r'^B\d+\s*[-–]?\s*', '', roteiro_texto).strip()
            if limpo:
                titulo = limpo
    
    titulo_limpo = re.sub(r'[^A-Za-z0-_=]', '_', titulo.upper())
    titulo_limpo = re.sub(r'_+', '_', titulo_limpo).strip('_')
    return f"BOLETIM_RADIO_TJRN_{dd}_{mm}_{aaaa}_B{numero}__{titulo_limpo}.mp3"


def extrair_info_nome(arquivo, transcricao_texto=None):
    """Extrai data e faixa de boletins do nome do arquivo e (opcionalmente) da transcrição.
    Retorna (data_str, B_ini, B_fim, data_completa_str)

    Data completa: DD_SET_AAAA (ex: 04_SET_2026)
    Se o filename tem "DD SET" e a transcrição tem "dia de setembro [de AAAA]", prefere a transcrição.
    Se filename tem apenas "DD SET" sem contexto, extrai do filename e assume ano atual ou 2026.
    """
    stem = Path(arquivo).stem

    # Extrair dia do filename: "18 SET", "04 SET", "17 SET", etc.
    m_data = re.search(r'(\d{1,2})\s*[Ss][Ee][Tt]', stem)
    dia_filename = m_data.group(1).zfill(2) if m_data else None

    # Extrair dia e ano da transcrição: "18 de setembro", "18 de setembro de 2026"
    dia_transcricao = None
    ano_transcricao = None
    if transcricao_texto:
        texto_clean = re.sub(r'\s+', ' ', transcricao_texto).lower()
        m_comp = re.search(r'(\d{1,2})\s*de\s+setembro\s*(?:de\s*(\d{4}))?', texto_clean)
        if m_comp:
            dia_transcricao = m_comp.group(1).zfill(2)
            ano_transcricao = m_comp.group(2) or None

    # Decidir qual usar: filename tem prioridade (mais confiável)
    # A transcrição pode conter datas de notícias (ex: "30 de setembro" no texto)
    if dia_filename:
        data_str = f"{dia_filename} SET"
        if ano_transcricao:
            data_completa_str = f"{dia_filename}_SET_{ano_transcricao}"
        else:
            data_completa_str = f"{dia_filename}_SET_{ANO_PADRAO}"
    elif dia_transcricao and ano_transcricao:
        data_str = f"{dia_transcricao} SET"
        data_completa_str = f"{dia_transcricao}_SET_{ano_transcricao}"
    elif dia_transcricao:
        data_str = f"{dia_filename} SET"
        # Se a transcrição só tem dia sem ano, usar ano do filename se tiver, ou 2026
        if dia_transcricao and not ano_transcricao:
            data_completa_str = f"{dia_transcricao}_SET_{ANO_PADRAO}"
        else:
            data_completa_str = None
    else:
        data_str = None
        data_completa_str = None

    # Se não consegui extrair data da transcrição e o filename tem um ano explícito
    # (ex: "18-09-2026" ou "18_09_2026" no nome), usar isso como fallback
    if data_completa_str is None:
        m_ano = re.search(r'(\d{2})[_-](\d{2})[_-](\d{4})', stem)
        if m_ano:
            data_completa_str = f"{m_ano.group(1)}_{m_ano.group(2).upper()}_{m_ano.group(3)}"
            if not data_str:
                data_str = f"{m_ano.group(1)} {m_ano.group(2).upper()}"

    # Fallback final: se ainda nada, usar o que tem
    if not data_completa_str:
        # Se só temos o dia do filename, assumir 2026
        if dia_filename:
            data_completa_str = f"{dia_filename}_SET_{ANO_PADRAO}"
        else:
            data_completa_str = "??_SET_????"

    # Faixa: "B6-B10", "B6 e B7", "B1 B5", "B1-B4", "B8-B10"...
    m_faixa = re.search(r'B(\d{1,2})\s*(?:[-–eE])\s*B(\d{1,2})', stem)
    if m_faixa:
        b_ini, b_fim = int(m_faixa.group(1)), int(m_faixa.group(2))
    else:
        m_faixa2 = re.search(r'(B\d{1,2})(B\d{1,2})', stem)
        if m_faixa2:
            b_ini, b_fim = int(m_faixa2.group(1)[1:]), int(m_faixa2.group(2)[1:])
        else:
            b_ini, b_fim = 1, 10  # fallback

    return data_str, b_ini, b_fim, data_completa_str


def carregar_roteiros(pasta_roteiros, data_str, b_ini, b_fim):
    """Se pasta_roteiros informado, busca roteiros .txt para cada boletim.
    Retorna dict {Bnumero: {"titulo": str, "cabeca": str, "off": str}}
    
    Formatos suportados:
    1. "B{N}- TITULO" por linha (formato compacto)
    2. "B{N}- TITULO\nCABEÇA: ...\nOFF: ..." (roteiro completo)
    """
    roteiros = {}
    if not pasta_roteiros or not pasta_roteiros.exists():
        return roteiros

    # Extrair dia da data_str (ex: "17 SET" -> "17")
    m_dia = re.search(r'(\d{1,2})', data_str)
    dia_str = m_dia.group(1) if m_dia else None

    # Priorizar arquivos com o dia no nome (ex: "roteiros_17_set.txt")
    arquivos = list(pasta_roteiros.glob("*.txt"))
    arquivos_ordenados = sorted(arquivos, key=lambda f: (
        0 if dia_str and dia_str in f.name else 1,
        len(f.name)  # arquivos menores primeiro (mais específicos)
    ))

    for f in arquivos_ordenados:
        texto = f.read_text(encoding="utf-8", errors="ignore")
        encontrou_algo = False
        
        # Formato 1: "B{N}- TITULO" por linha (formato compacto)
        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha:
                continue
            m = re.match(r'B(\d{1,2})\s*[-–—]\s*(.+)', linha)
            if m:
                n = int(m.group(1))
                if b_ini <= n <= b_fim:
                    titulo = m.group(2).strip()
                    if n not in roteiros or (dia_str and dia_str in f.name):
                        roteiros[n] = {"titulo": titulo, "cabeca": "", "off": ""}
                        encontrou_algo = True
        
        # Formato 2: "B{N}- TITULO\nCABEÇA: ...\nOFF: ..." (roteiro completo)
        blocos = re.split(r'={20,}|DOCUMENTO\s+\[\d+/\d+\]', texto)
        for bloco in blocos:
            m_b = re.search(r'B(\d{1,2})\s*[-–—]\s*(.+?)(?:\n|$)', bloco, re.I)
            m_cab = re.search(r'CABEÇA:\s*(.+?)(?:\n|$)', bloco, re.I)
            m_off = re.search(r'OFF:\s*(.+?)(?:\r?\n\r?\n|\Z)', bloco, re.I | re.DOTALL)
            if m_b:
                n = int(m_b.group(1))
                if b_ini <= n <= b_fim:
                    titulo = m_b.group(2).strip()
                    cabeca_texto = m_cab.group(1).strip() if m_cab else ""
                    off_texto = m_off.group(1).strip() if m_off else ""
                    # Sobrescrever se:
                    # - ainda não tem registro para este boletim, OU
                    # - o arquivo tem o dia no nome (prioridade), OU
                    # - o registro anterior não tinha OFF e este tem (mais completo)
                    deve_sobrescrever = (
                        n not in roteiros or
                        (dia_str and dia_str in f.name) or
                        (off_texto and not roteiros.get(n, {}).get("off"))
                    )
                    if deve_sobrescrever:
                        roteiros[n] = {"titulo": titulo, "cabeca": cabeca_texto, "off": off_texto}
                        encontrou_algo = True
        
        # Se encontrou todos os boletins neste arquivo E todos têm OFF, para
        # Caso contrário, continua procurando em outros arquivos (podem ter OFF)
        if encontrou_algo and len(roteiros) >= (b_fim - b_ini + 1):
            todos_tem_off = all(
                isinstance(v, dict) and v.get("off") for v in roteiros.values()
            )
            if todos_tem_off:
                break

    return roteiros


def processar_canonico(arquivo_entrada, pasta_roteiros=None):
    """Pipeline canônico completo. Retorna dict com resultados e estatísticas."""
    arquivo = Path(arquivo_entrada)
    if not arquivo.exists():
        return {"erro": f"Arquivo não encontrado: {arquivo}"}

    print(f"\n{'='*60}")
    print(f"PROCESSAMENTO CANÔNICO: {arquivo.name}")
    print(f"{'='*60}\n")

    # Carregar modelo Whisper uma vez (faster-whisper se disponível)
    print("Carregando modelo de transcrição...")
    modelo = carregar_modelo()

    # ETAPA 0: Triagem
    print("\n── ETAPA 0: TRIAGEM INICIAL DO ÁUDIO ──")
    audio = AudioSegment.from_mp3(str(arquivo))
    triagem = triagem_audio(audio)
    print(f"  Duração: {triagem['duracao_segundos']:.2f}s")
    print(f"  Canais: {triagem['canais']}, Samplerate: {triagem['frame_rate']}Hz")
    if triagem.get('acoes'):
        print(f"  Ações de correção: {triagem['acoes']}")

    # Aplicar correções de triagem (após transcrição, não antes)
    # NOTA: converter para mono ANTES da transcrição causa perda de qualidade
    # no Whisper (transcrições incompletas). Converter apenas para montagem.
    precisa_mono = triagem.get("canal_morto") or triagem.get("estereo_duplicado")

    # ETAPA 1: Transcrição
    print("\n── ETAPA 1: TRANSCRIÇÃO (Whisper base) ──")
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False, dir=str(TMP_DIR)) as tmp:
        tmp_path = tmp.name
    segmentos = transcrever(audio, tmp_path, modelo)

    # ETAPA 1.5: Correção de alucinações do Whisper
    print("\n── ETAPA 1.5: CORREÇÃO DE ALUCINAÇÕES ──")
    # Extrair faixa do nome do arquivo para carregar roteiros
    _, b_ini_f, b_fim_f, _ = extrair_info_nome(arquivo, None)
    # Compilar texto completo dos roteiros para correção
    texto_roteiro_completo = None
    if pasta_roteiros:
        roteiros_dict = carregar_roteiros(pasta_roteiros, "", b_ini_f, b_fim_f)
        if roteiros_dict:
            texto_roteiro_completo = " ".join(
                v["titulo"] + " " + v["off"] if isinstance(v, dict) else v
                for v in roteiros_dict.values()
            )

    segmentos_antes = len(segmentos)
    segmentos = corrigir_transcricao(segmentos, texto_roteiro_completo)
    removidos = segmentos_antes - len(segmentos)
    print(f"  Segmentos antes: {segmentos_antes}, depois: {len(segmentos)}, removidos: {removidos}")

    print(f"  Transcrito: {len(segmentos)} segmentos")
    print("\n  Transcrição completa:")
    for seg in segmentos:
        print(f"    [{seg['start']:7.2f}s - {seg['end']:7.2f}s] {seg['text'].strip()}")

    # ETAPA 2: Estrutura
    print("\n── ETAPA 2: DETECÇÃO DE ESTRUTURA ──")
    data_str, b_ini, b_fim, data_completa_str = extrair_info_nome(arquivo, " ".join(s["text"] for s in segmentos))
    if not data_completa_str or data_completa_str.startswith("??"):
        today = date.today()
        data_completa_str = f"{today.day:02d}_SET_{today.year}"
        data_str = f"{today.day} SET"
    print(f"  Data detectada: {data_str} → {data_completa_str}")
    print(f"  Faixa: B{b_ini} - B{b_fim}")

    roteiros = {}
    if pasta_roteiros:
        print(f"  Buscando roteiros em: {pasta_roteiros}")
        roteiros = carregar_roteiros(pasta_roteiros, data_str, b_ini, b_fim)
        print(f"  Roteiros encontrados: {len(roteiros)} boletins")

    estrutura = detectar_estrutura(segmentos, b_ini, b_fim)
    print(f"  Marcadores B{{N}}. encontrados: {list(estrutura['marcadores'].keys())}")
    print(f"  Assinaturas detectadas: {len(estrutura['assinaturas'])}")
    for t, nome, txt in estrutura['assinaturas']:
        print(f"    [{t:.2f}s] {nome} — {txt[:60]}")
    if estrutura['falta']:
        print(f"  Faltantes (interpolação): {estrutura['falta']}")

    # ETAPA 3: Repetições confirmadas
    print("\n── ETAPA 3: DETECÇÃO DE REPETIÇÕES (confirmação por áudio) ──")
    rep_confirmadas, rep_rejeitadas = detectar_repeticoes_confirmadas(segmentos, audio)
    print(f"  Repetições confirmadas: {len(rep_confirmadas)}")
    for r in rep_confirmadas:
        print(f"    [{r['inicio']:.2f}s - {r['fim']:.2f}s] similaridade={r['similaridade']:.2f} — '{r['texto_repetido'][:50]}'")
    print(f"  Repetições rejeitadas: {len(rep_rejeitadas)}")
    for r in rep_rejeitadas[:5]:
        print(f"    [{r['posicao']:.2f}s] {r['motivo'][:50]}")
    if len(rep_rejeitadas) > 5:
        print(f"    ... +{len(rep_rejeitadas)-5} mais")

    # ETAPA 4: Claquetes por assinatura
    print("\n── ETAPA 4: DETECÇÃO DE CLAKETES (gatilho por assinatura) ──")
    claquetes = detectar_claquetes_por_assinatura(segmentos, estrutura['assinaturas'], b_ini, b_fim)
    if "sem_deteccao" in claquetes:
        print(f"  Assinaturas sem claquete detectada nos próximos 5s: {len(claquetes['sem_deteccao'])}")
        for item in claquetes['sem_deteccao']:
            print(f"    [{item['tempo_assinatura']:.2f}s] {item['nome_reporter']}")
        del claquetes["sem_deteccao"]
    print(f"  Claquetes detectadas: {len([k for k in claquetes if isinstance(k, int)])}")
    for n, info in claquetes.items():
        if isinstance(n, int):
            print(f"    B{n}: [{info['inicio']:.2f}s - {info['fim']:.2f}s]")

    # ETAPA 4.5: Detectar claquete geral introdutória (B1)
    claquete_geral = detectar_claquete_geral(segmentos, b_ini, b_fim)
    if claquete_geral:
        print(f"\n── ETAPA 4.5: CLAQUETE GERAL DETECTADA ──")
        print(f"  Claquete geral: [{claquete_geral[0]:.2f}s - {claquete_geral[1]:.2f}s]")
        print(f"  Será removida do B1")
    else:
        print(f"\n── ETAPA 4.5: Claquete geral não detectada ──")

    # ETAPA 5: Corte e remoção (módulo especializado)
    print("\n── ETAPA 5: CORTE + REMOÇÃO ──")
    # Criar pasta de saída
    saida = arquivo.parent / f"{arquivo.stem}_saida"
    saida.mkdir(exist_ok=True)

    # Converter para mono se necessário (após transcrição, antes do corte)
    if precisa_mono:
        print(f"  Convertendo para mono (canal morto: {triagem.get('canal_morto')})")
        audio_corte = audio.set_channels(1) if triagem.get("estereo_duplicado") else audio.split_to_mono()[0 if triagem['canal_morto'] == 'direito' else 1].set_channels(1)
    else:
        audio_corte = audio

    # Processar cortes via módulo especializado
    boletims_cortados = processar_cortes_boletim(
        segmentos=segmentos,
        audio_corte=audio_corte,
        rep_confirmadas=rep_confirmadas,
        claquetes=claquetes,
        claquete_geral=claquete_geral,
        estrutura=estrutura,
        b_ini=b_ini,
        b_fim=b_fim
    )

    # Imprimir resumo dos cortes
    for n, info in boletims_cortados.items():
        rot_n = roteiros.get(n, {}) if roteiros else {}
        titulo_rot = rot_n.get("titulo", "") if isinstance(rot_n, dict) else rot_n
        nome_arquivo = nomear_boletim(data_str, n, titulo_rot, data_completa_str)
        print(f"  B{n}: [{info['inicio_original']:.2f}s → {info['fim_original']:.2f}s] = {info['duracao_cortada']:.2f}s → {nome_arquivo}")

    # ETAPA 6: Montagem com vinhetas
    print("\n── ETAPA 6: MONTAGEM COM VINHETAS ──")
    for n, info in boletims_cortados.items():
        if info['duracao_cortada'] < 3:
            print(f"  B{n}: skipping montagem (duração muito curta: {info['duracao_cortada']:.2f}s)")
            continue

        rot_n = roteiros.get(n, {}) if roteiros else {}
        titulo_rot = rot_n.get("titulo", "") if isinstance(rot_n, dict) else rot_n
        cabeca_rot = rot_n.get("cabeca", "") if isinstance(rot_n, dict) else ""
        nome_arquivo = nomear_boletim(data_str, n, titulo_rot, data_completa_str)
        info['nome'] = nome_arquivo
        
        # Calcular duração da cabeça baseada no roteiro (se disponível)
        # Usar o áudio original (com vinheta de abertura) para detectar a cabeça
        if cabeca_rot:
            duracao_cabeca = calcular_duracao_cabeca(audio, cabeca_rot, modelo)
            print(f"  B{n}: cabeça do roteiro = {duracao_cabeca:.1f}s")
        else:
            duracao_cabeca = 20  # fallback
        
        montado = montar_boletim_com_vinhetas(
            info['audio'],
            None, None, None,  # VHTs carregadas dentro da função
            duracao_cabeca
        )

        caminho_saida = saida / nome_arquivo
        montado.export(str(caminho_saida), format="mp3")
        print(f"  ✓ B{n}: montado → {nome_arquivo} ({len(montado)/1000:.2f}s)")

    # ETAPA 7: Auditoria
    print("\n── ETAPA 7: AUDITORIA ──")
    auditoria = {
        "arquivo_entrada": str(arquivo),
        "data_detectada": data_str,
        "faixa": [b_ini, b_fim],
        "duracao_original": triagem['duracao_segundos'],
        "triagem": triagem,
        "transcricao": {
            "segmentos": len(segmentos),
            "texto_completo": " ".join(s["text"].strip() for s in segmentos)
        },
        "estrutura": estrutura,
        "repeticoes": {
            "confirmadas": rep_confirmadas,
            "rejeitadas": rep_rejeitadas[:10]
        },
        "claquetes": {str(k): v for k, v in claquetes.items()},
        "boletims_gerados": []
    }

    for n in sorted(boletims_cortados.keys()):
        info = boletims_cortados[n]
        if 'nome' not in info:
            rot_n = roteiros.get(n, {}) if roteiros else {}
            titulo_rot = rot_n.get("titulo", "") if isinstance(rot_n, dict) else rot_n
            info['nome'] = nomear_boletim(data_str, n, titulo_rot, data_completa_str)
        caminho = saida / info['nome']
        try:
            if not caminho.exists():
                info['audio'].export(str(caminho), format="mp3")
            if caminho.exists():
                audio_b = AudioSegment.from_mp3(str(caminho))
                auditoria["boletims_gerados"].append({
                    "arquivo": info['nome'],
                    "duracao_segundos": round(len(audio_b)/1000, 2),
                    "tamanho_bytes": caminho.stat().st_size
                })
                print(f"  ✓ {info['nome']} — {len(audio_b)/1000:.2f}s, {caminho.stat().st_size/1024:.1f} KB")
            else:
                print(f"  ✗ ARQUIVO NÃO EXISTE: {caminho.name}")
        except Exception as e:
            print(f"  ✗ ERRO ao processar {info['nome']}: {e}")
            import traceback
            traceback.print_exc()
            # Garante que a chave exista mesmo em caso de erro
            if "boletims_gerados" not in auditoria:
                auditoria["boletims_gerados"] = []

    # ETAPA 7.5: Validação de qualidade da transcrição vs roteiro
    if roteiros:
        print(f"\n── ETAPA 7.5: VALIDAÇÃO DE QUALIDADE (transcrição vs roteiro) ──")
        from corrigir_alucinacoes import corrigir_transcricao as corrige_aluc
        from difflib import SequenceMatcher
        
        for n in sorted(boletims_cortados.keys()):
            info = boletims_cortados[n]
            caminho = saida / info['nome']
            if not caminho.exists() or caminho.stat().st_size < 1000:
                continue
            
            # Transcrever boletim editado
            tmp = tempfile.mktemp(suffix='.wav', dir=str(TMP_DIR))
            audio_b = AudioSegment.from_mp3(str(caminho))
            segmentos_transcritos = transcrever(audio_b, tmp, modelo)
            
            texto_transcrito = " ".join(s["text"] for s in segmentos_transcritos)
            
            # Obter texto do roteiro para este boletim (usar OFF)
            rot_n = roteiros.get(n, {}) if roteiros else {}
            if isinstance(rot_n, dict):
                roteiro_b = rot_n.get("off", "") or rot_n.get("titulo", "")
            else:
                roteiro_b = rot_n
            if not roteiro_b:
                continue
            
            # Calcular similaridade (usando cobertura do roteiro)
            texto_norm = normalizar_texto(texto_transcrito)
            roteiro_norm = normalizar_texto(roteiro_b)
            
            palavras_roteiro = set(roteiro_norm.split())
            palavras_transcrito = set(texto_norm.split())
            
            if palavras_roteiro:
                # Cobertura: % das palavras do roteiro que aparecem na transcrição
                cobertura = len(palavras_roteiro & palavras_transcrito) / len(palavras_roteiro)
            else:
                cobertura = 0.0
            
            sim_original = cobertura
            
            print(f"  B{n}: cobertura original = {sim_original:.2%}")
            
            # Se cobertura baixa (< 60%), aplicar correções e retranscrever
            # Threshold 60%: Whisper alucina nomes próprios (ex: "Tejota Reino" em vez de "TJRN")
            if sim_original < COBERTURA_MIN:
                print(f"  B{n}: cobertura baixa — aplicando correções de alucinações...")
                
                # Aplicar correções na transcrição
                segmentos_corrigidos = corrige_aluc(segmentos_transcritos, roteiro_b)
                texto_corrigido = " ".join(s.get("text", s.get("text_corrigido", "")).strip() for s in segmentos_corrigidos)
                texto_corrigido_norm = normalizar_texto(texto_corrigido)
                
                palavras_corrigido = set(texto_corrigido_norm.split())
                if palavras_roteiro:
                    cobertura_corrigida = len(palavras_roteiro & palavras_corrigido) / len(palavras_roteiro)
                else:
                    cobertura_corrigida = 0.0
                
                sim_corrigido = cobertura_corrigida
                
                print(f"  B{n}: cobertura corrigida = {sim_corrigido:.2%}")
                
                # Adicionar info na auditoria (cobertura = % do roteiro presente na transcrição)
                for bg in auditoria["boletims_gerados"]:
                    if f"_B{n}__" in bg["arquivo"]:
                        bg["qualidade"] = {
                            "cobertura_roteiro_original": round(sim_original, 3),
                            "cobertura_roteiro_corrigida": round(sim_corrigido, 3),
                            "correcoes_aplicadas": True,
                            "texto_corrigido": texto_corrigido[:500],
                            "nota": "Cobertura de palavras do roteiro. NAO substitui audicao humana."
                        }
                        break
            else:
                for bg in auditoria["boletims_gerados"]:
                    if f"_B{n}__" in bg["arquivo"]:
                        bg["qualidade"] = {
                            "cobertura_roteiro_original": round(sim_original, 3),
                            "correcoes_aplicadas": False,
                            "nota": "Cobertura de palavras do roteiro. NAO substitui audicao humana."
                        }
                        break

    # Salvar auditoria
    auditoria_path = saida / "auditoria.json"
    with open(auditoria_path, "w", encoding="utf-8") as f:
        json.dump(auditoria, f, indent=2, ensure_ascii=False)
    print(f"\n  Auditoria salva: {auditoria_path}")

    print(f"\n{'='*60}")
    print(f"PROCESSAMENTO COMPLETO: {len(auditoria['boletims_gerados'])} boletins gerados")
    print(f"Saída: {saida}")
    print(f"{'='*60}")
    print(f"\n⚠️  AUDITORIA HUMANA OBRIGATÓRIA ANTES DE ENTREGAR:")
    print(f"   1. Ouvir cada boletim gerado")
    print(f"   2. Verificar: sem repetições, sem claquetes, conteúdo faz sentido")
    print(f"   3. Cobertura de palavras NÃO substitui audição")
    print(f"   4. Se reprovações: ajustar pipeline e reprocessar")
    print(f"{'='*60}\n")

    return auditoria


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline canônico de edição de boletins")
    parser.add_argument("arquivo", help="Arquivo MP3 de entrada")
    parser.add_argument("--roteiros", help="Pasta com roteiros em texto (opcional)", default=None)
    args = parser.parse_args()

    pasta_roteiros = Path(args.roteiros) if args.roteiros else None
    # Se --roteiros for um arquivo, usar o diretório pai
    if pasta_roteiros and pasta_roteiros.is_file():
        pasta_roteiros = pasta_roteiros.parent
    resultado = processar_canonico(args.arquivo, pasta_roteiros)

    if "erro" in resultado:
        print(f"ERRO: {resultado['erro']}")
        sys.exit(1)
    
    # Garantir que a auditoria tenha a chave boletims_gerados para impressão final
    if "boletims_gerados" not in resultado:
        resultado["boletims_gerados"] = []
    print(f"PROCESSAMENTO COMPLETO: {len(resultado['boletims_gerados'])} boletins gerados")
