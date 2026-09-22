#!/usr/bin/env python3
"""
transcricao_cache.py — Cache de transcrição em disco.

Evita retranscrever áudios que não mudaram.
Hash do áudio (amostras + tamanho) como chave. Cache em JSON.

Uso:
    from shared.transcricao_cache import TranscricaoCache, calcular_hash_audio
    
    cache = TranscricaoCache()
    hash_audio = calcular_hash_audio(caminho_audio)
    
    segmentos = cache.obter(hash_audio)
    if segmentos is None:
        segmentos = whisper.transcribe(...)
        cache.salvar(hash_audio, segmentos)
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Optional


def calcular_hash_audio(caminho: Path, amostra_bytes: int = 1_000_000) -> str:
    """
    Calcula hash de um arquivo de amostras.
    
    Estratégia: hash dos primeiros N bytes + últimos N bytes + tamanho total.
    Detecta mudanças sem ler o arquivo inteiro.
    """
    tamanho = caminho.stat().st_size
    h = hashlib.sha256()
    
    with open(caminho, 'rb') as f:
        h.update(f.read(amostra_bytes))
        if tamanho > amostra_bytes * 2:
            f.seek(-amostra_bytes, 2)
            h.update(f.read(amostra_bytes))
    
    h.update(str(tamanho).encode())
    return h.hexdigest()


class TranscricaoCache:
    """Cache de transcrição em disco."""
    
    def __init__(self, dir_cache: Optional[Path] = None, max_entries: int = 100):
        if dir_cache is None:
            dir_cache = Path(os.environ.get("DIVISOR_CACHE_DIR", Path.home() / ".cache" / "divisor"))
        self.dir_cache = Path(dir_cache)
        self.max_entries = max_entries
        self.dir_cache.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0
    
    def _caminho_cache(self, hash_audio: str) -> Path:
        return self.dir_cache / f"{hash_audio}.json"
    
    def obter(self, hash_audio: str) -> Optional[list]:
        """Retorna segmentos cacheados ou None."""
        caminho = self._caminho_cache(hash_audio)
        if caminho.exists():
            self._hits += 1
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        self._misses += 1
        return None
    
    def salvar(self, hash_audio: str, segmentos: list):
        """Salva segmentos no cache."""
        caminho = self._caminho_cache(hash_audio)
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(segmentos, f, ensure_ascii=False, indent=2)
        self._limpar_antigos()
    
    def _limpar_antigos(self):
        """Remove entradas mais antigas se exceder max_entries."""
        entradas = sorted(self.dir_cache.glob("*.json"), key=lambda p: p.stat().st_mtime)
        while len(entradas) > self.max_entries:
            entradas[0].unlink()
            entradas.pop(0)
    
    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {"hits": self._hits, "misses": self._misses, "hit_rate": hit_rate}
    
    def limpar_tudo(self):
        """Remove todo o cache."""
        for f in self.dir_cache.glob("*.json"):
            f.unlink()
        self._hits = 0
        self._misses = 0


# Singleton
_cache: Optional[TranscricaoCache] = None


def get_cache() -> TranscricaoCache:
    """Retorna cache global (lazy load)."""
    global _cache
    if _cache is None:
        _cache = TranscricaoCache()
    return _cache
