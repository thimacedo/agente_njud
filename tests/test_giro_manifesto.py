"""Testes comportamentais do planejamento, gates e publicação GIRO."""
import copy
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from giro.controle_producao import (
    POLITICA, VINHETAS, carregar_json_giro, grade_giro, montar_manifesto_giro,
    planejar_giro, salvar_json_giro, sha256_giro, sincronizar_giro,
    validar_manifesto_giro,
)


def criar_manifesto(tmp_path):
    root = tmp_path / 'projeto'
    source = root / 'GIRO/input'
    notes = root / 'data/processed/GIRO/0902'
    source.mkdir(parents=True)
    notes.mkdir(parents=True)
    data = dict(grade_giro(2026, 9)[1], politica=POLITICA, versao='v01',
                autorizacoes={'incluir_natal': False}, notas=[])
    for i in range(1, 5):
        origem = source / f'BOLETIM_RADIO_TJRN_03_09_2026_B{i}_PAUTA.mp3'
        nota = notes / f'nota-{i}.wav'
        origem.write_bytes(f'origem{i}'.encode())
        nota.write_bytes(f'nota{i}'.encode())
        data['notas'].append({'ordem': i, 'pauta_id': f'pauta-{i}', 'titulo': f'Pauta {i}',
                              'boletim': f'B{i}', 'data_boletim': '2026-09-03',
                              'origem': str(origem), 'origem_sha256': sha256_giro(origem),
                              'audio_nota': str(nota), 'audio_sha256': sha256_giro(nota),
                              'geografia': {'uf': 'RN', 'municipio': 'Acari', 'classificacao': 'interior_rn', 'evidencia': 'Roteiro conferido'},
                              'limites': {'inicio_s': 1., 'fim_s': 76., 'evidencia': 'Escuta'},
                              'revisao': {'aprovada': True, 'responsavel': 'Editor teste', 'evidencia': 'Escuta',
                                          'loc_off_completos': True, 'sem_vinhetas_boletim': True}})
    return root, data


def duracao_mock(path):
    return 100. if Path(path).name.startswith('BOLETIM_') else 75.


def test_calendario_civil_inclui_quinta_terca_e_virada_ano():
    grade = grade_giro(2026, 9)
    assert [p['data_exibicao'] for p in grade] == ['2026-09-01', '2026-09-08', '2026-09-15', '2026-09-22', '2026-09-29']
    assert grade[-1]['codigo'] == '0905'
    assert grade[0]['janela_coleta']['inicio'] == '2026-08-26'
    assert grade_giro(2027, 1)[0]['janela_coleta']['inicio'] == '2026-12-30'
    assert grade_giro(2026, 7)[0]['codigo'] == '0701'


def test_planejamento_sem_escrita_revela_lacunas_e_nao_aprova(tmp_path):
    root = tmp_path / 'projeto'
    source = root / 'GIRO/input'
    source.mkdir(parents=True)
    names = ['BOLETIM_RADIO_TJRN_26_08_2026_B1_MARCELINO.mp3', '03 - SET - B1-B4.mp3',
             '090 SET B1-B5.mp3', 'BOLETIM_RADIO_TJRN_08_09_2026_B1_FORA.mp3']
    for name in names:
        (source / name).write_bytes(b'nao_decodificar')
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with patch('subprocess.run', side_effect=AssertionError('Não chamar áudio')):
        result = planejar_giro(2026, 9, [source, source, root / 'ausente'], root)
    after = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert before == after
    assert not (root / 'data').exists()
    assert result['edicoes'][0]['quantidade_arquivos'] == 1
    assert result['edicoes'][1]['quantidade_arquivos'] == 1
    assert result['edicoes'][2]['quantidade_arquivos'] == 0
    assert result['edicoes'][1]['notas'] == []
    assert any('090 SET' in aviso for aviso in result['avisos'])
    assert result['edicoes'][1]['fontes'][0]['formato'] == 'concatenado'
    assert result['edicoes'][1]['fontes'][0]['geografia'] == 'pendente'


def test_manifesto_preserva_ordem_aprovada(tmp_path):
    root, data = criar_manifesto(tmp_path)
    data['notas'][0], data['notas'][1] = data['notas'][1], data['notas'][0]
    for i, nota in enumerate(data['notas'], 1):
        nota['ordem'] = i
    with patch('giro.controle_producao.duracao_giro', side_effect=duracao_mock):
        notas = validar_manifesto_giro(data, root, root)
    assert notas[0].name == 'nota-2.wav'


@pytest.mark.parametrize('mutation', ['estado', 'ambigua', 'natal', 'natal_disfarce', 'revisao',
                                     'fora_janela', 'data_origem', 'hash', 'duplicada',
                                     'ordem', 'limites', 'duracao', 'isolamento', 'dia', 'janela', 'boletim', 'versao'])
def test_manifesto_interrompe_antes_da_montagem(tmp_path, mutation):
    root, data = criar_manifesto(tmp_path)
    n = data['notas'][0]
    if mutation == 'estado': n['geografia']['uf'] = 'CE'
    elif mutation == 'ambigua': n['geografia']['classificacao'] = 'ambigua'
    elif mutation == 'natal': n['geografia'].update(municipio='Natal', classificacao='natal')
    elif mutation == 'natal_disfarce': n['geografia']['municipio'] = 'Natal'
    elif mutation == 'revisao': n['revisao']['aprovada'] = False
    elif mutation == 'fora_janela': n['data_boletim'] = '2026-09-08'
    elif mutation == 'data_origem': n['data_boletim'] = '2026-09-04'
    elif mutation == 'hash': Path(n['origem']).write_bytes(b'alterada')
    elif mutation == 'duplicada': data['notas'][1]['pauta_id'] = n['pauta_id']
    elif mutation == 'ordem': n['ordem'] = 3
    elif mutation == 'limites': n['limites']['fim_s'] = 0.
    elif mutation == 'duracao': n['limites']['fim_s'] = 95.
    elif mutation == 'isolamento': n['audio_nota'] = str(root / 'NJUD/nota.wav')
    elif mutation == 'dia': data['data_exibicao'] = '2026-09-09'
    elif mutation == 'janela': data['janela_coleta']['fim'] = '2026-09-08'
    elif mutation == 'boletim': n['boletim'] = 'B8'
    elif mutation == 'versao': data['versao'] = '../NJUD'
    with patch('giro.controle_producao.duracao_giro', side_effect=duracao_mock):
        with pytest.raises((ValueError, OSError)):
            validar_manifesto_giro(data, root, root)
    assert not (root / 'data/output').exists()


def test_natal_so_com_autorizacao_explicita(tmp_path):
    root, data = criar_manifesto(tmp_path)
    data['notas'][0]['geografia'].update(municipio='Natal', classificacao='natal', justificativa='Faltam pautas do interior')
    data['autorizacoes']['incluir_natal'] = True
    with patch('giro.controle_producao.duracao_giro', side_effect=duracao_mock):
        assert len(validar_manifesto_giro(data, root, root)) == 4


def test_cli_planejamento_nao_importa_audio_e_nao_escreve(tmp_path):
    root = tmp_path / 'projeto'
    root.mkdir()
    script = Path(__file__).resolve().parents[1] / 'scripts_pipeline/executar_programa.py'
    proc = subprocess.run([sys.executable, '-B', str(script), '--raiz', str(root), 'planejar',
                           '--ano', '2026', '--mes', '9'], text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    assert len(json.loads(proc.stdout)['edicoes']) == 5
    assert list(root.iterdir()) == []


def test_json_nao_sobrescreve(tmp_path):
    path = tmp_path / 'plano.json'
    salvar_json_giro(path, {'original': True})
    with pytest.raises(FileExistsError):
        salvar_json_giro(path, {'original': False})
    assert carregar_json_giro(path) == {'original': True}


def test_montar_sem_apply_so_valida_e_nao_importa_montador(tmp_path, capsys):
    from giro.processo import main
    root, data = criar_manifesto(tmp_path)
    manifest = root / 'manifesto.json'
    salvar_json_giro(manifest, data)
    with patch('giro.controle_producao.duracao_giro', side_effect=duracao_mock), patch('giro.processo.montar_manifesto_giro', side_effect=AssertionError('Não montar')):
        assert main(['--raiz', str(root), 'montar', str(manifest)]) == 0
    assert not (root / 'data/output').exists()


def test_sync_sem_apply_nao_escreve(tmp_path):
    from giro.processo import main
    with patch('giro.processo.sincronizar_giro', side_effect=AssertionError('Não copiar')):
        assert main(['sync', str(tmp_path / 'candidato.json'), '--revisao', str(tmp_path / 'rev.json'),
                     '--destino', str(tmp_path / 'destino')]) == 2
    assert list(tmp_path.iterdir()) == []


def test_manifesto_extraido_nao_aprova_nem_monta(tmp_path, capsys):
    from giro.processo import main
    plan = planejar_giro(2026, 9, [], tmp_path)
    file = tmp_path / 'planejamento.json'
    salvar_json_giro(file, plan)
    assert main(['manifesto', str(file), '--codigo', '0905']) == 0
    draft = json.loads(capsys.readouterr().out)
    assert draft['notas'] == []
    with pytest.raises(ValueError, match='4 a 6'):
        validar_manifesto_giro(draft, tmp_path, tmp_path)


def test_backend_giro_sem_manifesto_nao_chama_audio(tmp_path, monkeypatch):
    import importlib.util
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path / 'upload'))
    monkeypatch.setenv('OUTPUT_DIR', str(tmp_path / 'output'))
    monkeypatch.setenv('SIMULATE', '0')
    path = Path(__file__).resolve().parents[1] / 'frontend/server.py'
    spec = importlib.util.spec_from_file_location('backend_giro_test', path)
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    backend.jobs['teste'] = {}
    monkeypatch.setattr(backend.time, 'sleep', lambda _: None)
    monkeypatch.setattr(backend, 'run_command', lambda *a, **k: pytest.fail('Não chamar montagem'))
    assert backend.run_pipeline_giro('teste', backend.UPLOAD_DIR, backend.OUTPUT_DIR) is None
    assert backend.jobs['teste']['status'] == 'error'
    assert list(backend.OUTPUT_DIR.iterdir()) == []


def test_montagem_real_candidato_e_sync_separado(tmp_path):
    from pydub import AudioSegment
    from pydub.generators import Sine
    root, data = criar_manifesto(tmp_path)
    # Sinais sintetizados somente na pasta temporária de teste, não acervo real.
    for i, n in enumerate(data['notas'], 1):
        AudioSegment.silent(duration=100000).export(n['origem'], format='mp3')
        (Sine(200+i*20).to_audio_segment(duration=75000).apply_gain(-20)).export(n['audio_nota'], format='wav')
        n['origem_sha256'] = sha256_giro(n['origem'])
        n['audio_sha256'] = sha256_giro(n['audio_nota'])
    assets = root / 'assets/vinhetas/giro'
    assets.mkdir(parents=True)
    for name in VINHETAS:
        Sine(500).to_audio_segment(duration=1000).apply_gain(-18).export(assets / name, format='mp3')
    manifesto = root / 'manifesto.json'
    salvar_json_giro(manifesto, data)
    candidato = montar_manifesto_giro(manifesto, root)
    report = carregar_json_giro(candidato)
    assert report['ordem_pautas'] == [n['pauta_id'] for n in data['notas']]
    assert report['status'] == 'candidato'
    assert report['sincronizado'] is False
    assert 305 <= report['duracao_s'] < 306
    with pytest.raises((ValueError, FileExistsError)):
        montar_manifesto_giro(manifesto, root)
    lock = candidato.parent / '.montagem.lock'
    assert not lock.exists()
    lock.write_text('outro processo')
    with pytest.raises(FileExistsError):
        montar_manifesto_giro(manifesto, root)
    assert lock.read_text() == 'outro processo'
    lock.unlink()
    destination = tmp_path / 'destino_externo'
    destination.mkdir()
    review = tmp_path / 'revisao.json'
    approval = {'aprovada': False, 'responsavel': 'Editor teste', 'evidencia_escuta': 'Sinal sintético verificado',
                'editorial_ok': True, 'sonoro_ok': True, 'candidato_sha256': sha256_giro(candidato),
                'arquivo_sha256': report['arquivo_sha256']}
    review.write_text(json.dumps(approval))
    with pytest.raises(ValueError, match='revisão final'):
        sincronizar_giro(candidato, review, destination, root)
    assert list(destination.iterdir()) == []
    approval['aprovada'] = True
    review.write_text(json.dumps(approval))
    copied = sincronizar_giro(candidato, review, destination, root)
    assert sha256_giro(copied) == report['arquivo_sha256']
    with pytest.raises(FileExistsError):
        sincronizar_giro(candidato, review, destination, root)
    Path(data['notas'][0]['origem']).write_bytes(b'fonte alterada')
    with pytest.raises(ValueError, match='alterado'):
        sincronizar_giro(candidato, review, destination, root)

def test_montagem_autorizada_nao_inventa_revisao(tmp_path):
    root, data = criar_manifesto(tmp_path)
    for nota in data['notas']:
        nota['revisao']['aprovada'] = False
    data['autorizacao_montagem_local'] = {'autorizada': True, 'responsavel': 'Usuario', 'mensagem': 'Montar candidatos locais', 'hashes_notas': [n['audio_sha256'] for n in data['notas']]}
    with patch('giro.controle_producao.duracao_giro', side_effect=duracao_mock):
        with pytest.raises(ValueError, match='revis'):
            validar_manifesto_giro(data, root, root)
        assert len(validar_manifesto_giro(data, root, root, permitir_montagem_local_autorizada=True)) == 4
        assert all(n['revisao']['aprovada'] is False for n in data['notas'])
        data['autorizacao_montagem_local']['hashes_notas'][0] = '0' * 64
        with pytest.raises(ValueError, match='revis'):
            validar_manifesto_giro(data, root, root, permitir_montagem_local_autorizada=True)


def test_montagem_autorizada_preserva_gate_geografico(tmp_path):
    root, data = criar_manifesto(tmp_path)
    data['autorizacao_montagem_local'] = {'autorizada': True, 'responsavel': 'Usuario', 'mensagem': 'Montar candidatos locais', 'hashes_notas': [n['audio_sha256'] for n in data['notas']]}
    data['notas'][0]['geografia']['uf'] = 'RS'
    with pytest.raises(ValueError):
        validar_manifesto_giro(data, root, root, permitir_montagem_local_autorizada=True)
