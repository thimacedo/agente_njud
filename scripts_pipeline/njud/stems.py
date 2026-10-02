"""Separa voz/acompanhamento no boletim individual, nunca no NJUD montado.

Dependências opcionais em ambiente isolado; pesos precisam estar locais.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .controle_producao import _ler_pcm, _salvar_pcm, salvar_json, sha256, validar_manifesto


def separar_manifesto(manifesto, destino, repositorio, modelo_id="955717e8", threads=4):
    import numpy as np
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    manifesto = validar_manifesto(manifesto)
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=False)
    repositorio = Path(repositorio)
    checkpoints = list(repositorio.glob(modelo_id + "-*.th"))
    if len(checkpoints) != 1:
        raise ValueError("Checkpoint local único obrigatório")
    model_hash = sha256(checkpoints[0])
    torch.set_num_threads(threads)
    model = get_model(modelo_id, repo=repositorio).cpu().eval()
    rate = model.samplerate
    result = []
    for item in manifesto["boletins"]:
        if sha256(item["origem"]) != item["sha256"]:
            raise ValueError("Fonte alterada antes dos stems")
        data = _ler_pcm(item["origem"], rate=rate)
        mix = torch.from_numpy(data.astype(np.float32).T)
        mono = mix.mean(0); mean = mono.mean(); std = mono.std()
        if float(std) < 1e-6:
            raise ValueError("Fonte silenciosa")
        with torch.no_grad():
            separated = apply_model(model, ((mix - mean) / std)[None],
                                    device="cpu", shifts=0, split=True,
                                    overlap=.25, progress=True, num_workers=0)[0]
        voice = (separated[model.sources.index("vocals")] * std + mean).T.numpy()
        # Acompanhamento residual conserva exatamente a soma com a voz.
        accompaniment = data - voice
        b = item["boletim"]
        vp = destino / f"B{b}_VOZ.wav"; ap = destino / f"B{b}_ACOMPANHAMENTO.wav"
        _salvar_pcm(vp, voice, rate); _salvar_pcm(ap, accompaniment, rate)
        if sha256(item["origem"]) != item["sha256"]:
            raise ValueError("Fonte alterada durante os stems")
        record = {"origem": item["origem"], "origem_sha256": item["sha256"],
                  "voz": str(vp.resolve()), "voz_sha256": sha256(vp),
                  "acompanhamento": str(ap.resolve()), "acompanhamento_sha256": sha256(ap),
                  "modelo": "htdemucs/" + modelo_id, "modelo_sha256": model_hash,
                  "torch": torch.__version__, "sample_rate": rate,
                  "duracao_s": len(data)/rate,
                  "erro_reconstrucao_max": float(np.max(np.abs(voice + accompaniment - data))),
                  "etapa": "boletim_individual_antes_dos_cortes_e_montagem",
                  "status": "candidato_pendente_auditoria"}
        salvar_json(destino / f"B{b}_stems.json", record)
        result.append(record)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifesto", type=Path)
    parser.add_argument("destino", type=Path)
    parser.add_argument("--repositorio-modelo", type=Path, required=True)
    parser.add_argument("--modelo-id", default="955717e8")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    result = separar_manifesto(json.loads(args.manifesto.read_text(encoding="utf-8")), args.destino,
                               args.repositorio_modelo, args.modelo_id, args.threads)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
