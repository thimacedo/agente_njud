#!/usr/bin/env python3
"""Spike 001: testa initial_prompt do Whisper para melhorar cobertura do roteiro."""
import whisper
import tempfile
import os
import json
import re
from pathlib import Path
from pydub import AudioSegment

# Config
AUDIO_PATH = r"E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\boletins\17 SET B1-B5-2_saida\BOLETIM_RADIO_TJRN_17_SET_2026_B1__TJRN_EMPRESA_DEVOLVER_VALORES_FALHA_COMPRA.mp3"

# OFF do roteiro B1 (para comparação)
ROTEIRO_OFF = """Uma empresa de tecnologia e varejo online terá que restituir valores pagos por uma consumidora após ela comprar produtos na plataforma e não recebê-los. Consta na sentença que a mulher adquiriu um notebook, no valor de R$ 1.199,90 e um jipe infantil elétrico, por R$ 949,90, entretanto, mesmo constando como entregue no sistema da ré, o notebook nunca foi recebido pela autora da ação. De acordo com os autos, a consumidora tentou exercer o direito de arrependimento em relação ao jipe, porém, não conseguiu efetuar o procedimento por sua conta ter sido bloqueada pela ré, inviabilizando a devolução e o reembolso. Já a empresa alegou a regularidade da prestação do serviço e afirmou que o notebook foi entregue no endereço da autora. O caso foi julgado pelo 4º Juizado Especial Cível e Criminal da Comarca de Mossoró. O juiz responsável pelo caso, destacou que a relação jurídica entre as partes é de consumo, levando em consideração o Código de Defesa do Consumidor. Ainda de acordo com o magistrado, mesmo com a ré afirmando que o notebook foi entregue em dezembro do ano passado segundo registros sistêmicos internos, essas provas são insuficientes para comprovar o adimplemento da obrigação."""

PROMPTS = {
    "sem_prompt": None,
    "prompt_curto": "Boletim informativo do Tribunal de Justiça do Rio Grande do Norte. Cidades: Natal, Mossoró, Caicó, Currais Novos, Pau dos Ferros, Macau, Assu, São Gonçalo do Amarante. Termos: apenado, remição, regressão de regime, tornozeleira eletrônica, falta grave.",
    "prompt_expandido": "Boletim informativo do Tribunal de Justiça do Rio Grande do Norte, TJRN. Comarcas: Natal, Mossoró, Caicó, Currais Novos, Pau dos Ferros, Macau, Assu, São Gonçalo do Amarante, João Câmara, Santa Cruz, Ceará-Mirim, Parnamirim, Macaíba, São José de Mipibu, Nísia Floresta, Goianinha, Vera Cruz, Montanhas, Tibau do Sul, Arês, Vila Flor. Termos jurídicos: apenado, apenada, remição de pena, regressão de regime, progressão de regime, tornozeleira eletrônica, falta grave, falta leve, advertência, curso EAD, ensino a distância, Projeto Político-Pedagógico, Conselho Nacional de Justiça, CNJ, Ministério Público, MPRN, Câmara Criminal, Vara Criminal, Vara de Execução Penal, Juizado Especial, consumidor, Código de Defesa do Consumidor, ré, réu, autora, autor, ação, sentença, recurso, convênio, sistema prisional, penitenciária, ressocialização.",
}

def normalizar(texto):
    import unicodedata
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

def calcular_cobertura(texto_transcrito, texto_roteiro):
    t_norm = set(normalizar(texto_transcrito).split())
    r_norm = set(normalizar(texto_roteiro).split())
    if not r_norm:
        return 0.0
    return len(r_norm & t_norm) / len(r_norm)

def transcrever(audio_path, initial_prompt=None):
    modelo = whisper.load_model("base")
    tmp = tempfile.mktemp(suffix=".wav", dir=r"C:\Users\THIAGO\AppData\Local\Temp")
    AudioSegment.from_mp3(audio_path).export(tmp, format="wav")
    
    kwargs = {"language": "pt", "fp16": False}
    if initial_prompt:
        kwargs["initial_prompt"] = initial_prompt
    
    result = modelo.transcribe(tmp, **kwargs)
    os.unlink(tmp)
    return result["text"].strip()

def main():
    print("=" * 60)
    print("SPIKE 001: whisper-initial-prompt")
    print("=" * 60)
    print(f"ÁUDIO: {Path(AUDIO_PATH).name}")
    print()
    
    resultados = {}
    
    for nome, prompt in PROMPTS.items():
        print(f"--- {nome} ---")
        if prompt:
            print(f"  Prompt: {prompt[:80]}...")
        else:
            print(f"  Prompt: (nenhum)")
        
        texto = transcrever(AUDIO_PATH, prompt)
        cobertura = calcular_cobertura(texto, ROTEIRO_OFF)
        resultados[nome] = {"cobertura": cobertura, "texto": texto[:200]}
        
        print(f"  Cobertura: {cobertura:.2%}")
        print(f"  Transcrição (início): {texto[:150]}...")
        print()
    
    # Resumo
    print("=" * 60)
    print("RESUMO")
    print("=" * 60)
    for nome, r in resultados.items():
        print(f"  {nome:20s}: {r['cobertura']:.2%}")
    
    # Salvar resultados
    out_path = Path(__file__).parent / "resultados.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"\nResultados salvos em: {out_path}")

if __name__ == "__main__":
    main()
