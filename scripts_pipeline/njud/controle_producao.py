"""Preparação rastreável NJUD: limpeza ANTES da montagem e aprendizado revisado.

Nunca aprova automaticamente a qualidade sonora. Não modifica fontes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import uuid

POLITICA = "njud-pre-montagem-2"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def salvar_json(path, data):
    # Artefatos imutáveis: nunca sobrescrever versões anteriores.
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)


def validar_manifesto(data):
    date.fromisoformat(data["data_edicao"])
    date.fromisoformat(data["data_boletins"])
    if not isinstance(data["njud"], int) or data["njud"] <= 0:
        raise ValueError("Número NJUD inválido")
    items = data["boletins"]
    if len(items) != 4 or len({i["boletim"] for i in items}) != 4:
        raise ValueError("Exatamente quatro boletins distintos, em ordem editorial")
    if not data.get("versao") or not data.get("referencia_passagem"):
        raise ValueError("Versão e referência de passagem obrigatórias")
    for item in items:
        if sha256(item["origem"]) != item["sha256"]:
            raise ValueError("Fonte alterada: " + item["origem"])
        limites = item["limites"]
        points = [limites[k] for k in ("cabeca_inicio", "cabeca_fim", "corpo_inicio", "corpo_fim")]
        if any(not isinstance(t, (int, float)) or not math.isfinite(t) for t in points):
            raise ValueError("Limites devem ser tempos finitos")
        if not 0 <= points[0] < points[1] <= points[2] < points[3]:
            raise ValueError("Limites ausentes, invertidos ou sobrepostos")
        if not limites.get("evidencia"):
            raise ValueError("Cortes precisam de evidência registrada")
        if item.get("stems"):
            stem = item["stems"]
            if stem["origem_sha256"] != item["sha256"] or sha256(stem["voz"]) != stem["voz_sha256"]:
                raise ValueError("Stem não corresponde à origem ou foi alterado")
            if sha256(stem["acompanhamento"]) != stem["acompanhamento_sha256"]:
                raise ValueError("Acompanhamento de auditoria alterado")
            if not limites.get("evidencia_fim_frase"):
                raise ValueError("Stem exige conferência do fim da frase, além do timestamp ASR")
    return data


def validar_grade(manifestos):
    datas = [m["data_edicao"] for m in manifestos]
    numeros = [m["njud"] for m in manifestos]
    if len(set(datas)) != len(datas) or len(set(numeros)) != len(numeros):
        raise ValueError("Grade duplicada: uma edição por data e número")


def _ler_pcm(path, rate=48000):
    import numpy as np
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(rate), "-"],
        capture_output=True, check=True,
    )
    return np.frombuffer(result.stdout, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def limpar_referencia(audio, ref, limites, rate=48000):
    """Cancela somente a passagem conhecida; rejeita correlação fraca/voz na calibração."""
    import numpy as np
    from scipy.signal import correlate
    n = len(ref)
    # Janela restrita à transição marcada; não procurar correspondências em outras falas.
    lo = max(0, int((limites["cabeca_fim"] - .2) * rate))
    hi = min(len(audio), int((limites["corpo_inicio"] + 2) * rate))
    if hi - lo < n:
        raise ValueError("Janela de passagem insuficiente")
    mono = audio[lo:hi].mean(axis=1)
    template = ref.mean(axis=1)
    energy_ref = float(np.dot(template, template))
    if energy_ref <= 1e-12:
        raise ValueError("Referência silenciosa")
    corr = correlate(mono, template, mode="valid", method="fft")
    cs = np.r_[0., np.cumsum(mono ** 2)]
    scores = corr / np.sqrt(np.maximum((cs[n:] - cs[:-n]) * energy_ref, 1e-20))
    index = int(np.argmax(scores)); score = float(scores[index]); pos = lo + index
    if score < .90:
        raise ValueError(f"Passagem não confiável ({score:.3f}); revisar ou testar stems antes da montagem")
    # Estimar ganho apenas depois da manchete e ANTES da primeira palavra do corpo.
    start = max(240, int(limites["cabeca_fim"] * rate) - pos + 240)
    end = min(n, int(limites["corpo_inicio"] * rate) - pos - 240)
    if end - start < rate * .2:
        raise ValueError("Sem janela instrumental de 200 ms: usar revisão/stems")
    output = audio.copy(); gains = []
    for channel in range(2):
        rr = ref[start:end, channel]; xx = audio[pos + start:pos + end, channel]
        denominator = float(np.dot(rr, rr))
        if denominator < 1e-12:
            raise ValueError("Canal da referência silencioso")
        gain = float(np.dot(xx, rr) / denominator)
        if not .1 <= gain <= 2:
            raise ValueError("Ganho fora da faixa validada")
        output[pos:pos+n, channel] -= gain * ref[:, channel]
        gains.append(gain)
    before = audio[pos + start:pos + end]; after = output[pos + start:pos + end]
    reduction = float(10 * np.log10(max(float(np.sum(after ** 2)), 1e-20) / max(float(np.sum(before ** 2)), 1e-20)))
    if reduction > -15:
        raise ValueError(f"Resíduo instrumental alto ({reduction:.1f} dB): revisar/stems")
    if float(np.max(np.abs(output))) > 1:
        raise ValueError("Limpeza causou saturação; revisão obrigatória")
    return output, {"inicio_s": pos/rate, "fim_s": (pos+n)/rate,
                    "correlacao": score, "ganhos": gains, "reducao_instrumental_db": reduction,
                    "escuta_pendente": True, "metodo": "referencia_alinhada"}


def _salvar_pcm(path, samples, rate=48000):
    import numpy as np
    result = subprocess.run(
        ["ffmpeg", "-n", "-v", "error", "-f", "f32le", "-ar", str(rate), "-ac", "2", "-i", "-",
         "-c:a", "pcm_s24le", str(path)],
        input=samples.astype(np.float32).tobytes(), capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))


def preparar(data, destino):
    """Fontes -> cópias -> limpeza -> cortes WAV -> manifesto para montador canônico."""
    data = validar_manifesto(data)
    if any(not i.get("stems") for i in data["boletins"]) and data.get("fontes_sem_bg_confirmadas") is not True:
        raise ValueError("Boletins misturados exigem stems antes da montagem. A referência só é suficiente em fontes já confirmadas sem BG.")
    destino = Path(destino).resolve()
    # Saídas separadas; destino novo e nunca dentro de uma pasta de fontes.
    for item in data["boletins"]:
        source_parent = Path(item["origem"]).resolve().parent
        if destino == source_parent or source_parent in destino.parents:
            raise ValueError("Saída deve ficar separada da origem")
    destino.mkdir(parents=True, exist_ok=False)
    for name in ("fontes", "limpos", "cortes", "auditoria"):
        (destino/name).mkdir()
    salvar_json(destino/"manifesto_entrada.json", data)
    refpath = Path(data["referencia_passagem"])
    reference_hash = sha256(refpath)
    ref = _ler_pcm(refpath) if any(not i.get("stems") for i in data["boletins"]) else None
    pares = []; reports = []
    try:
        for order, item in enumerate(data["boletins"], 1):
            copy = destino/"fontes"/f"N{order}_{Path(item['origem']).name}"
            shutil.copy2(item["origem"], copy)
            if sha256(copy) != item["sha256"]:
                raise ValueError("Cópia divergente")
            audio = _ler_pcm(copy); limits = item["limites"]
            if limits["corpo_fim"] > len(audio)/48000:
                raise ValueError("Corte fora do áudio")
            if item.get("stems"):
                cleaned = _ler_pcm(item["stems"]["voz"])
                if abs(len(cleaned) - len(audio)) > 2:
                    raise ValueError("Stem mudou duração/alinhamento da origem")
                report = {"metodo": "stems_pre_montagem", "modelo": item["stems"]["modelo"],
                          "modelo_sha256": item["stems"]["modelo_sha256"],
                          "voz_sha256": item["stems"]["voz_sha256"],
                          "acompanhamento_sha256": item["stems"]["acompanhamento_sha256"],
                          "escuta_pendente": True, "evidencia_fim_frase": limits["evidencia_fim_frase"]}
            else:
                cleaned, report = limpar_referencia(audio, ref, limits)
            wav = destino/"limpos"/f"N{order}_B{item['boletim']}.wav"
            _salvar_pcm(wav, cleaned)
            pair = {"boletim": item["boletim"], "origem_sha256": item["sha256"]}
            for kind, prefix in (("cabeca", "CABECA"), ("corpo", "CORPO")):
                ini = int(limits[kind+"_inicio"]*48000)
                fim = int(limits[kind+"_fim"]*48000)
                cut = destino/"cortes"/f"N{order}_B{item['boletim']}_{prefix}.wav"
                _salvar_pcm(cut, cleaned[ini:fim])
                pair[kind] = str(cut); pair[kind+"_sha256"] = sha256(cut)
            pares.append(pair); reports.append({"boletim": item["boletim"], **report})
            if sha256(item["origem"]) != item["sha256"]:
                raise ValueError("Fonte mudou durante o processamento")
        if sha256(refpath) != reference_hash:
            raise ValueError("Referência mudou durante o processamento")
        prepared = {"politica": POLITICA, "njud": data["njud"], "data_edicao": data["data_edicao"],
                    "data_boletins": data["data_boletins"], "versao": data["versao"],
                    "pares": pares, "status": "candidato_pendente_auditoria", "master_aprovado": False,
                    "referencia_sha256": reference_hash, "limpeza": reports}
        salvar_json(destino/"manifesto_producao.json", prepared)
        return prepared
    except Exception as exc:
        salvar_json(destino/"auditoria"/"falha.json", {"erro": str(exc), "politica": POLITICA, "status": "refazer"})
        raise


def carregar_pares(pasta):
    """Só aceita peças do manifesto, na ordem editorial e com hash intacto."""
    pasta = Path(pasta).resolve()
    data = json.loads((pasta/"manifesto_producao.json").read_text(encoding="utf-8"))
    if data.get("politica") not in (POLITICA, "njud-pre-montagem-1") or len(data["pares"]) != 4:
        raise ValueError("Manifesto de produção inválido")
    date.fromisoformat(data["data_edicao"])
    if len({p["boletim"] for p in data["pares"]}) != 4:
        raise ValueError("Boletim duplicado")
    pairs = []
    for pair in data["pares"]:
        paths = []
        for kind in ("cabeca", "corpo"):
            path = Path(pair[kind]).resolve()
            if pasta not in path.parents or sha256(path) != pair[kind+"_sha256"]:
                raise ValueError("Corte fora do lote ou alterado")
            paths.append(path)
        pairs.append(tuple(paths))
    return data, pairs


def registrar_revisao(arquivo, pasta_aprendizado, auditor, resultado, motivo, checks=None):
    """Aprendizado por eventos imutáveis. Aprovação humana vinculada ao hash da versão."""
    if resultado not in ("aprovado", "refazer") or not auditor.strip() or not motivo.strip():
        raise ValueError("Resultado, auditor e motivo obrigatórios")
    checks = checks or {}
    required = ("escuta_integral", "cortes_sem_residuos", "voz_preservada", "conteudo_ordem_data", "apresentacao_editorial", "duracao")
    if resultado == "aprovado" and not all(checks.get(k) is True for k in required):
        raise ValueError("Aprovação exige todas as verificações, inclusive escuta e conteúdo editorial")
    if resultado == "aprovado":
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(arquivo)], capture_output=True, text=True, check=True)
        if not 0 < float(json.loads(probe.stdout)["format"]["duration"]) <= 300:
            raise ValueError("Duração real impede aprovação")
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(arquivo), "-f", "null", "-"], capture_output=True, check=True)
    event = {"id": uuid.uuid4().hex, "momento": datetime.now(timezone.utc).isoformat(),
             "politica": POLITICA, "arquivo": str(Path(arquivo).resolve()), "sha256": sha256(arquivo),
             "auditor": auditor, "resultado": resultado, "motivo": motivo, "checks": checks}
    destino = Path(pasta_aprendizado); destino.mkdir(parents=True, exist_ok=True)
    salvar_json(destino/(event["id"]+".json"), event)
    return event


def resumo_aprendizado(pasta):
    events = [json.loads(p.read_text(encoding="utf-8")) for p in Path(pasta).glob("*.json")]
    failures = Counter(e["motivo"] for e in events if e.get("resultado") == "refazer")
    return {"eventos": len(events), "aprovacoes": sum(e.get("resultado") == "aprovado" for e in events),
            "politicas_observadas": sorted({e.get("politica", "desconhecida") for e in events}),
            "motivos_retrabalho": dict(failures),
            "acao": "Revisar causas recorrentes; propor política nova e validar em piloto. Sem ajuste automático de parâmetros."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    prep = sub.add_parser("preparar"); prep.add_argument("manifesto", type=Path); prep.add_argument("destino", type=Path)
    rev = sub.add_parser("revisar"); rev.add_argument("arquivo", type=Path); rev.add_argument("aprendizado", type=Path)
    rev.add_argument("--auditor", required=True); rev.add_argument("--resultado", required=True, choices=("aprovado", "refazer"))
    rev.add_argument("--motivo", required=True); rev.add_argument("--checks", type=Path)
    res = sub.add_parser("aprendizado"); res.add_argument("pasta", type=Path)
    args = parser.parse_args()
    if args.comando == "preparar":
        result = preparar(json.loads(args.manifesto.read_text(encoding="utf-8")), args.destino)
    elif args.comando == "revisar":
        checks = json.loads(args.checks.read_text(encoding="utf-8")) if args.checks else {}
        result = registrar_revisao(args.arquivo, args.aprendizado, args.auditor, args.resultado, args.motivo, checks)
    else:
        result = resumo_aprendizado(args.pasta)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
