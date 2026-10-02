"""Planejamento e controle editorial GIRO. Não importa os pipelines legados."""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

PROGRAMA_GIRO = 'GIRO'
POLITICA = 'giro-manifesto-1'
VINHETAS = ('VHT_ABERTURA_GIRO.mp3', 'VHT_PASSAGEM_GIRO.mp3', 'VHT_ENCERRAMENTO_GIRO.mp3')


def raiz_giro():
    return Path(os.environ.get('DIVISOR_BASE_DIR', Path(__file__).resolve().parents[2])).resolve()


def sha256_giro(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def carregar_json_giro(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def salvar_json_giro(path, data):
    """Escrita explícita, sem sobrescrever e sem deixar JSON parcial."""
    path = Path(path)
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        try:
            stream.write(payload)
        except BaseException:
            stream.close()
            path.unlink(missing_ok=True)
            raise


def grade_giro(ano, mes):
    datas = [date(ano, mes, dia) for dia in range(1, calendar.monthrange(ano, mes)[1] + 1)
             if date(ano, mes, dia).weekday() == 1]
    return [{'programa': PROGRAMA_GIRO, 'codigo': f'{mes:02d}{i:02d}',
             'data_exibicao': d.isoformat(),
             'janela_coleta': {'inicio': (d - timedelta(days=6)).isoformat(),
                               'fim': (d - timedelta(days=1)).isoformat(), 'dias_totais': 6}}
            for i, d in enumerate(datas, 1)]


def validar_edicao_giro(data):
    if data.get('programa') != PROGRAMA_GIRO or data.get('politica') != POLITICA:
        raise ValueError('Manifesto precisa ser GIRO e usar a política vigente')
    exibicao = date.fromisoformat(data['data_exibicao'])
    esperado = next((p for p in grade_giro(exibicao.year, exibicao.month)
                     if p['data_exibicao'] == exibicao.isoformat()), None)
    if esperado is None or data['codigo'] != esperado['codigo']:
        raise ValueError('Código/data não correspondem à terça real do mês')
    if data['janela_coleta'] != esperado['janela_coleta']:
        raise ValueError('Janela deve ser [X-6, X-1], inclusive')
    return exibicao, date.fromisoformat(esperado['janela_coleta']['inicio']), date.fromisoformat(esperado['janela_coleta']['fim'])


def dados_nome_giro(nome, ano):
    canonical = re.match(r'^BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_(B\d+)_(.+)\.mp3$', nome, re.I)
    if canonical:
        dia, mes, year, numero, titulo = canonical.groups()
        return date(int(year), int(mes), int(dia)), numero.upper(), titulo, 'individualizado'
    raw = re.match(r'^(\d{2})\s*[- ]*([A-Z]{3})\s*[- ]*B(\d+)(?:\s*[- ]*B?(\d+)|\s*E\s*B?(\d+))?\.mp3$', nome, re.I)
    if raw:
        dia, mes_nome, primeiro, ultimo, ultimo_e = raw.groups()
        meses = dict(zip(('JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'), range(1, 13)))
        if mes_nome.upper() not in meses:
            return None
        end = int(ultimo or ultimo_e or primeiro)
        if end < int(primeiro):
            raise ValueError('Faixa de boletins invertida')
        return date(ano, meses[mes_nome.upper()], int(dia)), f'B{primeiro}-B{end}', '', 'concatenado'
    return None


def planejar_giro(ano, mes, fontes, raiz=None):
    """Somente leitura, inclusive sem mkdir, locks, caches ou chamadas de áudio."""
    raiz = Path(raiz or raiz_giro()).resolve()
    grade = grade_giro(ano, mes)
    inventario, avisos, vistos = [], [], set()
    for fonte in fontes:
        fonte = Path(fonte).resolve()
        if not fonte.is_dir():
            avisos.append(f'Fonte ausente ou inacessível: {fonte}')
            continue
        try:
            for path in sorted(fonte.rglob('*')):
                if not path.is_file() or path.suffix.lower() != '.mp3':
                    continue
                if path.resolve() in vistos:
                    continue
                vistos.add(path.resolve())
                try:
                    extraido = dados_nome_giro(path.name, ano)
                except ValueError as exc:
                    avisos.append(f'Nome/data inválidos: {path.name}: {exc}')
                    continue
                if extraido is None:
                    avisos.append(f'Não classificado; confirmar data/peça: {path.name}')
                    continue
                data, boletim, titulo, formato = extraido
                if any(date.fromisoformat(p['janela_coleta']['inicio']) <= data <= date.fromisoformat(p['janela_coleta']['fim']) for p in grade):
                    inventario.append({'origem': str(path), 'data': data.isoformat(), 'boletim': boletim,
                                       'titulo': titulo, 'formato': formato, 'bytes': path.stat().st_size,
                                       'geografia': 'pendente', 'revisao_editorial': 'pendente'})
        except OSError as exc:
            avisos.append(f'Inventário incompleto em {fonte}: {exc}')
    chaves = Counter((i['data'], i['boletim'], i['titulo']) for i in inventario)
    for p in grade:
        inicio, fim = p['janela_coleta']['inicio'], p['janela_coleta']['fim']
        itens = [i for i in inventario if inicio <= i['data'] <= fim]
        p.update({'fontes': itens, 'datas_com_arquivos': sorted({i['data'] for i in itens}),
                  'datas_sem_arquivos': [(date.fromisoformat(inicio) + timedelta(days=n)).isoformat()
                                        for n in range(6) if (date.fromisoformat(inicio) + timedelta(days=n)).isoformat() not in {i['data'] for i in itens}],
                  'notas': [], 'autorizacoes': {'incluir_natal': False},
                  'politica': POLITICA, 'versao': 'v01', 'status': 'aguardando_selecao_editorial',
                  'quantidade_arquivos': len(itens),
                  'duplicatas_possiveis': [list(k) for k, count in chaves.items() if count > 1 and inicio <= k[0] <= fim]})
    required = ['scripts_pipeline/giro/processo.py', 'scripts_pipeline/giro/montagem.py']
    return {'programa': PROGRAMA_GIRO, 'politica': POLITICA, 'ano': ano, 'mes': mes,
            'modo': 'somente_leitura', 'edicoes': grade, 'avisos': avisos,
            'dependencias_ausentes': [p for p in required if not (raiz / p).is_file()],
            'vinhetas_ausentes': [v for v in VINHETAS if not (raiz / 'assets/vinhetas/giro' / v).is_file()],
            'observacoes': ['Quantidade de arquivos não equivale a notas elegíveis.',
                            'Data de concatenado sem ano exige confirmação editorial.',
                            'Datas sem arquivo não comprovam ausência de produção.',
                            'Geografia, duplicação de conteúdo e qualidade sonora exigem revisão.']}


def caminho_giro(valor, base):
    p = Path(valor)
    return (p if p.is_absolute() else Path(base) / p).resolve()


def dentro_giro(path, raiz):
    return Path(path).resolve().is_relative_to(Path(raiz).resolve())


def verificar_hash_giro(path, digest):
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest) or sha256_giro(path) != digest:
        raise ValueError(f'Arquivo alterado ou hash ausente: {path}')


def duracao_giro(path):
    proc = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                           '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    duracao = float(json.loads(proc.stdout)['format']['duration'])
    if not math.isfinite(duracao) or duracao <= 0:
        raise ValueError(f'Áudio vazio/inválido: {path}')
    return duracao


def validar_manifesto_giro(data, base, raiz=None, *, permitir_montagem_local_autorizada=False):
    """Aprovação editorial é explícita; o programa nunca a infere pelo título."""
    raiz = Path(raiz or raiz_giro()).resolve()
    _, inicio, fim = validar_edicao_giro(data)
    if not isinstance(data.get('versao'), str) or not re.fullmatch(r'v\d{2,}', data['versao']):
        raise ValueError('Versão obrigatória no formato v01')
    notas = data.get('notas', [])
    if not 4 <= len(notas) <= 6:
        raise ValueError('GIRO exige 4 a 6 notas aprovadas')
    autorizacao = data.get('autorizacao_montagem_local', {})
    montagem_autorizada = (
        permitir_montagem_local_autorizada
        and autorizacao.get('autorizada') is True
        and autorizacao.get('responsavel')
        and autorizacao.get('mensagem')
        and autorizacao.get('hashes_notas') == [n.get('audio_sha256') for n in notas]
    )
    ids, hashes_notas, referencias, boletins = set(), set(), set(), set()
    arquivos = []
    for index, nota in enumerate(notas, 1):
        if nota.get('ordem') != index:
            raise ValueError('Ordem editorial deve ser explícita e consecutiva')
        if not nota.get('pauta_id') or nota['pauta_id'] in ids:
            raise ValueError('Pauta ausente ou duplicada')
        ids.add(nota['pauta_id'])
        if not inicio <= date.fromisoformat(nota['data_boletim']) <= fim:
            raise ValueError('Nota fora da janela de coleta')
        if not nota.get('titulo') or not nota.get('boletim'):
            raise ValueError('Título e boletim obrigatórios')
        geo = nota.get('geografia', {})
        if geo.get('uf') != 'RN' or geo.get('classificacao') not in ('interior_rn', 'natal') or not geo.get('municipio') or not geo.get('evidencia'):
            raise ValueError('Geografia pendente, ambígua ou fora do RN')
        cidade = geo['municipio'].casefold().strip()
        if cidade == 'natal' and geo['classificacao'] != 'natal':
            raise ValueError('Natal não pode ser classificado como interior')
        if geo['classificacao'] == 'natal' and (cidade != 'natal' or data.get('autorizacoes', {}).get('incluir_natal') is not True or not geo.get('justificativa')):
            raise ValueError('Natal exige autorização editorial e justificativa')
        revisao = nota.get('revisao', {})
        if not montagem_autorizada and (revisao.get('aprovada') is not True or not revisao.get('responsavel') or not revisao.get('evidencia') or revisao.get('loc_off_completos') is not True or revisao.get('sem_vinhetas_boletim') is not True):
            raise ValueError('Nota requer revisão editorial e sonora explícita')
        origem = caminho_giro(nota['origem'], base)
        audio = caminho_giro(nota['audio_nota'], base)
        if not any(dentro_giro(audio, raiz / sub) for sub in ('GIRO/output', 'data/processed/GIRO', 'data/output/GIRO')):
            raise ValueError('Nota preparada deve estar isolada em GIRO')
        if audio.name.startswith('GNC_'):
            raise ValueError('Programa final não pode ser usado como nota')
        verificar_hash_giro(origem, nota.get('origem_sha256'))
        verificar_hash_giro(audio, nota.get('audio_sha256'))
        boletim_key = (nota['data_boletim'], nota['origem_sha256'], nota['boletim'])
        if boletim_key in boletins:
            raise ValueError('Boletim repetido na edição')
        boletins.add(boletim_key)
        limites = nota.get('limites', {})
        tempos = [limites.get(k) for k in ('inicio_s', 'fim_s')]
        if any(isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) for t in tempos) or not 0 <= tempos[0] < tempos[1] or not limites.get('evidencia'):
            raise ValueError('Limites finitos e evidência de corte obrigatórios')
        origem_dur = duracao_giro(origem)
        nota_dur = duracao_giro(audio)
        if tempos[1] > origem_dur + .1 or abs(nota_dur - (tempos[1] - tempos[0])) > .5:
            raise ValueError('Duração da nota não corresponde aos limites da origem')
        ref = (str(origem), tempos[0], tempos[1])
        if ref in referencias or nota['audio_sha256'] in hashes_notas:
            raise ValueError('Nota/corte duplicado')
        if any(path == str(origem) and tempos[0] < end and start < tempos[1] for path, start, end in referencias):
            raise ValueError('Cortes sobrepostos na mesma origem')
        referencias.add(ref)
        hashes_notas.add(nota['audio_sha256'])
        extraido = dados_nome_giro(origem.name, inicio.year)
        if extraido and extraido[0].isoformat() != nota['data_boletim']:
            raise ValueError('Data declarada difere do nome da origem')
        if extraido and extraido[3] == 'individualizado' and extraido[1] != nota['boletim']:
            raise ValueError('Boletim declarado difere do nome da origem')
        if extraido and extraido[3] == 'concatenado':
            faixa = re.fullmatch(r'B(\d+)-B(\d+)', extraido[1])
            numero = re.fullmatch(r'B(\d+)', nota['boletim'])
            if not numero or not int(faixa[1]) <= int(numero[1]) <= int(faixa[2]):
                raise ValueError('Boletim declarado fora da faixa da origem')
        if extraido is None and not nota.get('evidencia_data'):
            raise ValueError('Origem com nome irregular exige evidência da data')
        arquivos.append(audio)
    return arquivos


def montar_manifesto_giro(manifesto, raiz=None):
    raiz = Path(raiz or raiz_giro()).resolve()
    manifesto = Path(manifesto).resolve()
    digest_manifesto = sha256_giro(manifesto)
    data = carregar_json_giro(manifesto)
    notas = validar_manifesto_giro(data, manifesto.parent, raiz, permitir_montagem_local_autorizada=True)
    versao = data.get('versao')
    if not isinstance(versao, str) or not re.fullmatch(r'v\d{2,}', versao):
        raise ValueError('Versão obrigatória no formato v01')
    pasta = raiz / 'data/output/GIRO' / data['codigo'] / versao
    if not dentro_giro(pasta, raiz / 'data/output/GIRO'):
        raise ValueError('Saída fora de GIRO')
    pasta.mkdir(parents=True, exist_ok=True)
    lock = pasta / '.montagem.lock'
    with lock.open('x') as stream:
        stream.write(digest_manifesto)
    temporario = pasta / ('.candidato-' + uuid.uuid4().hex + '.mp3')
    try:
        if list(pasta.glob('GNC_*.mp3')) or (pasta / 'candidato.json').exists():
            raise ValueError('Versão existente; use uma nova versão')
        from pydub import AudioSegment
        from pydub.effects import normalize
        assets = raiz / 'assets/vinhetas/giro'
        assets_hash = {v: sha256_giro(assets / v) for v in VINHETAS}
        abertura, passagem, encerramento = [AudioSegment.from_file(assets / v) for v in VINHETAS]
        resultado = abertura
        for i, path in enumerate(notas):
            if i:
                resultado += passagem
            resultado += normalize(AudioSegment.from_file(path))
        resultado += encerramento
        if not 300 <= len(resultado) / 1000 <= 900:
            raise ValueError('GIRO deve ter 5 a 15 minutos; revise a seleção')
        # Verificar novamente fontes e manifesto após leitura/decodificação.
        validar_manifesto_giro(data, manifesto.parent, raiz, permitir_montagem_local_autorizada=True)
        verificar_hash_giro(manifesto, digest_manifesto)
        for nome, digest in assets_hash.items():
            verificar_hash_giro(assets / nome, digest)
        resultado.export(temporario, format='mp3', bitrate='192k',
                         parameters=['-af', 'loudnorm=I=-16:TP=-2:LRA=11', '-ar', '44100'])
        duracao = duracao_giro(temporario)
        if not 300 <= duracao <= 900:
            raise ValueError('Duração exportada fora da faixa de produção')
        exibicao = date.fromisoformat(data['data_exibicao'])
        nome = f"GNC_{data['codigo']}_{exibicao.strftime('%d-%m-%Y')}.mp3"
        saida = pasta / nome
        # rename em Windows não sobrescreve; o lock impede concorrência do processo.
        temporario.rename(saida)
        report = {'programa': PROGRAMA_GIRO, 'politica': POLITICA, 'status': 'candidato',
                  'codigo': data['codigo'], 'data_exibicao': data['data_exibicao'], 'versao': versao,
                  'arquivo': nome, 'arquivo_sha256': sha256_giro(saida), 'duracao_s': duracao,
                  'manifesto': str(manifesto), 'manifesto_sha256': digest_manifesto,
                  'vinhetas_sha256': assets_hash, 'ordem_pautas': [n['pauta_id'] for n in data['notas']],
                  'revisao_final': 'pendente', 'sincronizado': False,
                  'masterizacao': {'integrated_lufs': -16, 'true_peak_dbtp': -2, 'bitrate': '192k', 'sample_rate': 44100},
                  'autorizacao_montagem_local': data.get('autorizacao_montagem_local'),
                  'revisao_notas_aprovada': all(n.get('revisao', {}).get('aprovada') is True for n in data['notas'])}
        try:
            salvar_json_giro(pasta / 'candidato.json', report)
        except BaseException:
            saida.unlink(missing_ok=True)
            raise
        return pasta / 'candidato.json'
    finally:
        temporario.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


def sincronizar_giro(candidato, revisao, destino, raiz=None):
    """Único escritor externo GIRO: um candidato aprovado, sem glob/sobrescrita."""
    raiz = Path(raiz or raiz_giro()).resolve()
    candidato = Path(candidato).resolve()
    if not dentro_giro(candidato, raiz / 'data/output/GIRO'):
        raise ValueError('Candidato fora da saída isolada GIRO')
    data = carregar_json_giro(candidato)
    revisao = carregar_json_giro(revisao)
    if data.get('programa') != PROGRAMA_GIRO or data.get('politica') != POLITICA or data.get('status') != 'candidato':
        raise ValueError('Relatório não é um candidato GIRO vigente')
    if revisao.get('aprovada') is not True or not revisao.get('responsavel') or not revisao.get('evidencia_escuta') or revisao.get('editorial_ok') is not True or revisao.get('sonoro_ok') is not True:
        raise ValueError('Sincronização exige revisão final editorial e sonora')
    if revisao.get('candidato_sha256') != sha256_giro(candidato) or revisao.get('arquivo_sha256') != data['arquivo_sha256']:
        raise ValueError('Revisão não corresponde ao candidato')
    fonte = caminho_giro(data['arquivo'], candidato.parent)
    if fonte.parent != candidato.parent or not fonte.name.startswith(f"GNC_{data['codigo']}_"):
        raise ValueError('Arquivo candidato inválido')
    verificar_hash_giro(fonte, data['arquivo_sha256'])
    manifesto = caminho_giro(data['manifesto'], candidato.parent)
    verificar_hash_giro(manifesto, data['manifesto_sha256'])
    validar_manifesto_giro(carregar_json_giro(manifesto), manifesto.parent, raiz, permitir_montagem_local_autorizada=True)
    for nome, digest in data['vinhetas_sha256'].items():
        if nome not in VINHETAS:
            raise ValueError('Vinheta desconhecida')
        verificar_hash_giro(raiz / 'assets/vinhetas/giro' / nome, digest)
    if not 300 <= duracao_giro(fonte) <= 900:
        raise ValueError('Duração final inválida')
    destino = Path(destino).resolve()
    if dentro_giro(destino, raiz):
        raise ValueError('Destino de sincronização deve ser externo ao projeto')
    if not destino.is_dir():
        raise ValueError('Destino não existe ou não está acessível')
    alvo = destino / fonte.name
    with alvo.open('xb') as stream:
        try:
            with fonte.open('rb') as origem:
                shutil.copyfileobj(origem, stream)
            stream.flush()
            os.fsync(stream.fileno())
            verificar_hash_giro(alvo, data['arquivo_sha256'])
        except BaseException:
            stream.close()
            alvo.unlink(missing_ok=True)
            raise
    return alvo


