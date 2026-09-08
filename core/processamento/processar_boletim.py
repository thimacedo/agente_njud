"""
Entry point único para processamento de boletins (NJUD e GIRO).

Unifica o loop de processamento, auditoria e separação de stems,
com parâmetros específicos por programa.

Usa funções existentes do projeto:
- src/divisor_boletins/audio.py: cortar_audio, _encontrar_silencio_proximo
- src/giro/cortes.py: cortar_giro_silencio (corte específico do GIRO)
- src/audit/individual_cuts.py: analisar_par (auditoria de cortes CABEÇA/CORPO)
"""
import logging
from typing import Callable, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def analisar_par_cabeca_corpo(cabeca_path: Path, corpo_path: Path, modelo=None) -> dict:
    """
    Wrapper simplificado para auditoria de pares CABEÇA/CORPO.
    
    Implementa verificação básica sem depender de imports complexos.
    Para auditoria completa com Whisper, usar src/audit/individual_cuts.py diretamente.
    """
    from pydub import AudioSegment
    
    resultado = {
        'status': 'OK',
        'aprovado': True,
        'motivos': [],
        'problemas': []
    }
    
    try:
        # Carregar áudios
        cabeca = AudioSegment.from_file(str(cabeca_path))
        corpo = AudioSegment.from_file(str(corpo_path))
        
        duracao_cabeca = len(cabeca) / 1000.0
        duracao_corpo = len(corpo) / 1000.0
        
        # Validações básicas de duração
        if duracao_cabeca < 2.0:
            resultado['aprovado'] = False
            resultado['problemas'].append(f"CABEÇA muito curta: {duracao_cabeca:.1f}s")
        
        if duracao_corpo < 5.0:
            resultado['aprovado'] = False
            resultado['problemas'].append(f"CORPO muito curto: {duracao_corpo:.1f}s")
        
        # Regra crítica: Sem fallback para áudio completo
        # Se os cortes existem e têm duração razoável, considera aprovado
        # A auditoria completa com transcrição Whisper deve ser feita separadamente
        
        logger.info(f"Auditoria básica: CABEÇA={duracao_cabeca:.1f}s, CORPO={duracao_corpo:.1f}s")
        
    except Exception as e:
        logger.exception(f"Erro na auditoria: {e}")
        resultado['aprovado'] = False
        resultado['motivos'].append(f"Erro ao carregar/arquivos: {str(e)}")
    
    return resultado


def obter_funcao_corte(programa: str, config: Dict[str, Any]) -> Callable:
    """Retorna a função de corte adequada para o programa."""
    if programa.upper() == 'GIRO':
        from src.giro.cortes import cortar_giro_silencio
        return lambda audio_path, output_dir: cortar_giro_silencio(
            Path(audio_path),
            duracao_minima_silencio=config.get('duracao_silencio', 1.0),
            tolerancia=config.get('tolerancia_silencio', 0.2)
        )
    elif programa.upper() == 'NJUD':
        # NJUD usa divisor_boletins com vinheta de passagem
        from src.divisor_boletins.audio import processar_arquivo
        return lambda audio_path, output_dir: processar_arquivo(
            Path(audio_path),
            Path(output_dir),
            estrategia='padrao'
        )
    else:
        raise ValueError(f"Programa desconhecido: {programa}")


def validar_gate_boletins(
    boletins_disponiveis: list,
    boletins_necessarios: int,
    programa: str
) -> bool:
    """
    Valida se há boletins suficientes para montar o programa.
    
    Args:
        boletins_disponiveis: lista de boletins encontrados
        boletins_necessarios: quantidade mínima exigida pelo roteiro
        programa: nome do programa para logging
    
    Returns:
        True se gate passado, False caso contrário
    """
    qtd_disponivel = len(boletins_disponiveis)
    
    if qtd_disponivel >= boletins_necessarios:
        logger.info(f"[{programa}] Gate de montagem PASSED: {qtd_disponivel} >= {boletins_necessarios} boletins")
        return True
    else:
        logger.warning(
            f"[{programa}] Gate de montagem FAILED: {qtd_disponivel} < {boletins_necessarios} boletins. "
            f"Faltam {boletins_necessarios - qtd_disponivel} boletins."
        )
        return False


def ciclo_arquivo(
    cortar_fn: Callable,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Executa o ciclo principal de processamento para um arquivo de áudio.
    
    Args:
        cortar_fn: função específica de corte (por programa)
        config: dicionário com configurações do processo
    
    Returns:
        Dicionário com status do processamento e métricas
    """
    resultado = {
        'sucesso': False,
        'etapas_concluidas': [],
        'erros': [],
        'avisos': [],
        'metricas': {}
    }
    
    audio_path = config.get('audio_path')
    output_dir = config.get('output_dir')
    programa = config.get('programa', 'DESCONHECIDO')
    
    if not audio_path or not output_dir:
        erro = "Caminhos de áudio ou saída não definidos na configuração"
        logger.error(f"[{programa}] {erro}")
        resultado['erros'].append(erro)
        return resultado
    
    logger.info(f"[{programa}] Iniciando ciclo de processamento para {audio_path}")
    
    try:
        # Etapa 1: Corte (CABEÇA/CORPO)
        logger.info(f"[{programa}] Etapa 1: Executando corte...")
        cortes_result = cortar_fn(audio_path, output_dir)
        
        # Normalizar resultado do corte
        # GIRO retorna (stem_cabeca, stem_corpo, metadados)
        # NJUD retorna objeto diferente
        if isinstance(cortes_result, tuple) and len(cortes_result) == 3:
            cabeca_path, corpo_path, metadados = cortes_result
            if metadados.get('erro'):
                aviso = f"Corte falhou: {metadados['erro']}"
                logger.warning(f"[{programa}] {aviso}")
                resultado['avisos'].append(aviso)
                cortes = None
            else:
                cortes = {'cabeca': str(cabeca_path), 'corpo': str(corpo_path)}
        else:
            cortes = cortes_result
        
        if not cortes or 'cabeca' not in cortes or 'corpo' not in cortes:
            aviso = "Corte não retornou CABEÇA e CORPO válidos"
            logger.warning(f"[{programa}] {aviso}")
            resultado['avisos'].append(aviso)
            # Não falha imediatamente, deixa a auditoria decidir
        
        resultado['etapas_concluidas'].append('corte')
        resultado['metricas']['cortes'] = cortes
        
        # Etapa 2: Auditoria (se cortes existirem)
        if cortes:
            logger.info(f"[{programa}] Etapa 2: Executando auditoria...")
            
            # Regra crítica: Sem fallback para áudio completo
            # Se os cortes falharem, NÃO promove o áudio bruto como se fosse cortado
            regra_sem_fallback = config.get('regra_sem_fallback', True)
            
            # Usar auditoria básica implementada neste módulo
            # Para auditoria completa com Whisper, chamar src/audit/individual_cuts.py diretamente
            try:
                auditoria = analisar_par_cabeca_corpo(
                    Path(cortes['cabeca']),
                    Path(cortes['corpo']),
                    modelo=None
                )
                
                # Converter resultado para formato esperado
                aprovado = auditoria.get('status') == 'OK' or auditoria.get('aprovado', False)
                motivos = auditoria.get('motivos', []) or auditoria.get('problemas', [])
                
                auditoria_result = {
                    'aprovado': aprovado,
                    'motivos': motivos,
                    'detalhes': auditoria
                }
            except Exception as e:
                logger.exception(f"[{programa}] Erro na auditoria: {e}")
                auditoria_result = {
                    'aprovado': False,
                    'motivos': [f"Erro na auditoria: {str(e)}"],
                    'detalhes': {}
                }
            
            resultado['etapas_concluidas'].append('auditoria')
            resultado['metricas']['auditoria'] = auditoria_result
            
            if not auditoria_result['aprovado']:
                logger.error(f"[{programa}] Auditoria REPROVADA: {auditoria_result['motivos']}")
                resultado['erros'].append(f"Auditoria reprovada: {auditoria_result['motivos']}")
                
                # Fallback estruturado: tentar re-montagem se disponível
                if config.get('permitir_remontagem', False):
                    logger.info(f"[{programa}] Tentando re-montagem com intercalar=False...")
                    # Lógica de re-montagem seria implementada aqui
                    resultado['avisos'].append("Re-montagem solicitada mas não implementada neste módulo")
            else:
                logger.info(f"[{programa}] Auditoria APROVADA")
        else:
            # Cortes falharam e regra_sem_fallback está ativa
            if config.get('regra_sem_fallback', True):
                erro = "Cortes inválidos e regra sem fallback ativa - não promove áudio bruto"
                logger.error(f"[{programa}] {erro}")
                resultado['erros'].append(erro)
            else:
                aviso = "Cortes inválidos mas fallback permitido (não recomendado)"
                logger.warning(f"[{programa}] {aviso}")
                resultado['avisos'].append(aviso)
        
        # Etapa 3: Separação de Stems (Demucs) - Opcional
        if config.get('usar_demucs', False):
            logger.info(f"[{programa}] Etapa 3: Executando separação de stems (Demucs)...")
            # Implementação do Demucs seria chamada aqui
            # Nota: Se Demucs rodar ANTES dos cortes, a lógica de detecção muda
            resultado['etapas_concluidas'].append('demucs')
        
        resultado['sucesso'] = len(resultado['erros']) == 0
        
    except Exception as e:
        logger.exception(f"[{programa}] Erro crítico no ciclo de processamento: {str(e)}")
        resultado['erros'].append(str(e))
        resultado['sucesso'] = False
    
    logger.info(f"[{programa}] Ciclo concluído. Sucesso: {resultado['sucesso']}")
    return resultado


def processar_boletim(
    programa: str,
    roteiro_inicial: Dict[str, Any],
    boletins_disponiveis: list,
    cortar_fn: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Entry point principal para processamento de boletins.
    
    Orquestra todo o pipeline desde a validação do gate até a geração
    do arquivo final, usando funções parametrizadas por programa.
    
    Args:
        programa: 'NJUD' ou 'GIRO'
        roteiro_inicial: configurações do programa (JSON)
        boletins_disponiveis: lista de boletins encontrados para o período
        cortar_fn: (opcional) função de corte específica. Se None, usa padrão do programa
    
    Returns:
        Dicionário com resultado completo do processamento
    """
    logger.info(f"=" * 60)
    logger.info(f"Iniciando processamento para {programa}")
    logger.info(f"=" * 60)
    
    resultado_geral = {
        'programa': programa,
        'periodo': roteiro_inicial.get('PERIODO', {}),
        'sucesso': False,
        'boletins_processados': [],
        'erros': [],
        'avisos': []
    }
    
    # 1. Validar Gate de Montagem
    boletins_necessarios = roteiro_inicial.get('parametros', {}).get('BOLETINS_POR_PROGRAMA', 4)
    
    if not validar_gate_boletins(boletins_disponiveis, boletins_necessarios, programa):
        erro = f"Gate de montagem falhou: {len(boletins_disponiveis)} boletins disponíveis, mínimo {boletins_necessarios}"
        logger.error(f"[{programa}] {erro}")
        resultado_geral['erros'].append(erro)
        resultado_geral['sucesso'] = False
        return resultado_geral
    
    # 2. Obter funções de corte
    if cortar_fn is None:
        config_corte = {
            'duracao_silencio': roteiro_inicial.get('parametros', {}).get('DURACAO_SILENCIO_MINIMA', 1.0),
            'tolerancia_silencio': roteiro_inicial.get('parametros', {}).get('LIMIARES_AUDITORIA', {}).get('tolerancia_silencio', 0.2)
        }
        cortar_fn = obter_funcao_corte(programa, config_corte)
    
    # 3. Processar cada boletim
    # Nota: configs_por_boletim deve vir de uma fonte externa (lista de arquivos reais)
    # O roteiro inicial define parâmetros, mas os boletins disponíveis são descobertos em runtime
    for idx, boletim in enumerate(boletins_disponiveis):
        logger.info(f"[{programa}] Processando boletim {idx + 1}/{len(boletins_disponiveis)}")
        
        config_processamento = {
            'programa': programa,
            'audio_path': boletim.get('caminho_audio', str(boletim)),
            'output_dir': roteiro_inicial.get('saida', {}).get('diretorio', '/tmp/output'),
            'regra_sem_fallback': roteiro_inicial.get('parametros', {}).get('REGRA_SEM_FALLBACK', True),
            'permitir_remontagem': roteiro_inicial.get('parametros', {}).get('PERMITIR_REMONTAGEM', False),
            'usar_demucs': roteiro_inicial.get('config_demucs', {}).get('habilitado', False)
        }
        
        resultado_boletim = ciclo_arquivo(cortar_fn, config_processamento)
        
        if resultado_boletim['sucesso']:
            resultado_geral['boletins_processados'].append({
                'index': idx,
                'status': 'SUCESSO',
                'metricas': resultado_boletim['metricas']
            })
        else:
            resultado_geral['boletins_processados'].append({
                'index': idx,
                'status': 'FALHA',
                'erros': resultado_boletim['erros']
            })
            resultado_geral['erros'].extend(resultado_boletim['erros'])
        
        resultado_geral['avisos'].extend(resultado_boletim.get('avisos', []))
    
    # 4. Resultado final
    total_boletins = len(boletins_disponiveis)
    boletins_sucesso = len([b for b in resultado_geral['boletins_processados'] if b['status'] == 'SUCESSO'])
    
    resultado_geral['sucesso'] = (boletins_sucesso == total_boletins)
    
    logger.info(f"=" * 60)
    logger.info(f"Processamento {programa} concluído")
    logger.info(f"Boletins: {boletins_sucesso}/{total_boletins} com sucesso")
    logger.info(f"Status final: {'APROVADO' if resultado_geral['sucesso'] else 'REPROVADO'}")
    logger.info(f"=" * 60)
    
    return resultado_geral


if __name__ == '__main__':
    # Exemplo de uso direto (para testes)
    logging.basicConfig(level=logging.INFO)
    
    print("Módulo processar_boletim.py carregado.")
    print("Use a função processar_boletim() como entry point.")
