"""
Utilitários de tratamento de erros com retry exponencial e isolamento de falhas
"""
import time
import functools
from typing import Callable, Any, Optional, Tuple
from datetime import datetime


class RetryError(Exception):
    """Exceção lançada quando todas as tentativas de retry falham."""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Exception, ...] = (Exception,),
    logger: Optional[Any] = None
):
    """
    Decorador para retry exponencial em caso de falha.
    
    Args:
        max_retries: Número máximo de tentativas
        base_delay: Delay inicial em segundos
        backoff_factor: Multiplicador do delay a cada retry
        exceptions: Tupla de exceções que devem triggerar retry
        logger: Logger opcional para registrar tentativas
    
    Returns:
        Função decorada com retry automático
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def operacao_arriscada():
            # código que pode falhar
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if logger:
                        logger.warning(
                            f"Tentativa {attempt}/{max_retries} falhou para {func.__name__}: {e}"
                        )
                    else:
                        print(f"Tentativa {attempt}/{max_retries} falhou: {e}")
                    
                    if attempt < max_retries:
                        delay = base_delay * (backoff_factor ** (attempt - 1))
                        if logger:
                            logger.info(f"Aguardando {delay:.2f}s antes da próxima tentativa...")
                        time.sleep(delay)
            
            error_msg = f"{func.__name__} falhou após {max_retries} tentativas: {last_exception}"
            if logger:
                logger.error(error_msg)
            raise RetryError(error_msg)
        
        return wrapper
    return decorator


def isolate_failures(
    items: list,
    process_func: Callable,
    on_error: Optional[Callable[[Any, Exception], None]] = None,
    logger: Optional[Any] = None
) -> Tuple[list, list]:
    """
    Processa lista de itens isolando falhas individuais.
    
    Args:
        items: Lista de itens a processar
        process_func: Função para processar cada item
        on_error: Callback opcional chamado quando item falha
        logger: Logger opcional
    
    Returns:
        Tupla (sucessos, falhas) onde:
            - sucessos: lista de resultados bem-sucedidos
            - falhas: lista de tuplas (item, exceção)
    
    Example:
        def processar_arquivo(caminho):
            # processa arquivo
            return True
        
        sucessos, falhas = isolate_failures(arquivos, processar_arquivo)
    """
    sucessos = []
    falhas = []
    
    for item in items:
        try:
            resultado = process_func(item)
            sucessos.append((item, resultado))
            
            if logger:
                logger.debug(f"Item processado com sucesso: {item}")
        except Exception as e:
            falhas.append((item, e))
            
            if logger:
                logger.error(f"Falha ao processar {item}: {e}")
            else:
                print(f"Falha ao processar {item}: {e}")
            
            if on_error:
                try:
                    on_error(item, e)
                except Exception as callback_error:
                    if logger:
                        logger.error(f"Erro no callback de erro: {callback_error}")
    
    return sucessos, falhas


def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    logger: Optional[Any] = None,
    **kwargs
) -> Any:
    """
    Executa função capturando exceções e retornando valor padrão em caso de erro.
    
    Args:
        func: Função a executar
        *args: Argumentos posicionais para a função
        default: Valor a retornar em caso de erro
        logger: Logger opcional
        **kwargs: Argumentos nomeados para a função
    
    Returns:
        Resultado da função ou valor padrão se falhar
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if logger:
            logger.error(f"Erro em {func.__name__}: {e}")
        else:
            print(f"Erro em {func.__name__}: {e}")
        return default


class ErrorTracker:
    """Rastreia erros ocorridos durante execução do pipeline."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.start_time = datetime.now()
    
    def add_error(self, stage: str, message: str, exception: Optional[Exception] = None):
        """Registra um erro."""
        error = {
            'timestamp': datetime.now().isoformat(),
            'stage': stage,
            'message': message,
            'exception': str(exception) if exception else None
        }
        self.errors.append(error)
    
    def add_warning(self, stage: str, message: str):
        """Registra um warning."""
        warning = {
            'timestamp': datetime.now().isoformat(),
            'stage': stage,
            'message': message
        }
        self.warnings.append(warning)
    
    def has_errors(self) -> bool:
        """Verifica se há erros registrados."""
        return len(self.errors) > 0
    
    def get_summary(self) -> dict:
        """Retorna resumo dos erros e warnings."""
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings),
            'errors': self.errors,
            'warnings': self.warnings
        }
    
    def clear(self):
        """Limpa todos os registros."""
        self.errors = []
        self.warnings = []
        self.start_time = datetime.now()
