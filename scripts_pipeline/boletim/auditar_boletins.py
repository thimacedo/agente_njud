#!/usr/bin/env python3
"""Audita boletins comparando texto transcrito com roteiro esperado."""

import whisper
from pathlib import Path
from pydub import AudioSegment
import tempfile, os, re

# Roteiro esperado (texto normalizado)
ROTEIROS = {
    1: {
        "cabeca": "Empresa terá que devolver valores e indenizar cliente por falha em compras online",
        "off": """Uma empresa de tecnologia e varejo online terá que restituir valores pagos por uma consumidora após ela comprar produtos na plataforma e não recebê-los. Consta na sentença que a mulher adquiriu um notebook, no valor de R$ 1.199,90 e um jipe infantil elétrico, por R$ 949,90, entretanto, mesmo constando como entregue no sistema da ré, o notebook nunca foi recebido pela autora da ação.
De acordo com os autos, a consumidora tentou exercer o direito de arrependimento em relação ao jipe, porém, não conseguiu efetuar o procedimento por sua conta ter sido bloqueada pela ré, inviabilizando a devolução e o reembolso. Já a empresa alegou a regularidade da prestação do serviço e afirmou que o notebook foi entregue no endereço da autora. O caso foi julgado pelo 4º Juizado Especial Cível e Criminal da Comarca de Mossoró.
O juiz responsável pelo caso, destacou que a relação jurídica entre as partes é de consumo, levando em consideração o Código de Defesa do Consumidor. Ainda de acordo com o magistrado, mesmo com a ré afirmando que o notebook foi entregue em dezembro do ano passado segundo registros sistêmicos internos, essas provas são insuficientes para comprovar o adimplemento da obrigação."""
    },
    2: {
        "cabeca": "TJRN reforma decisão e nega remição de pena por curso sem convênio com sistema prisional",
        "off": """A Câmara Criminal do TJRN reformou decisão da 3ª Vara Regional de Execução Penal de Mossoró e negou a remição de nove dias de pena concedida a um apenado pela realização de curso na modalidade de Ensino a Distância. Ao acolher recurso do Ministério Público, o colegiado entendeu que a instituição responsável pelo curso não possuía convênio com o sistema prisional nem integrava o Projeto Político-Pedagógico da unitário prisional, requisitos previstos para o reconhecimento do benefício.
Segundo a decisão, a Resolução do Conselho Nacional de Justiça admite a remição de pena por atividades educacionais, inclusive cursos de capacitação profissional, desde que observadas as regras estabelecidas para garantir a finalidade de ressocialização do apenado.
Conforme o relator, a participação em cursos na modalidade EAD, por si só, não assegura o direito à remição da pena. Além de ser reconhecida pelo Ministério da Educação, a instituição de ensino deve estar integrada ao Projeto Político-Pedagógico da unidade prisional ou manter convênio com o sistema penitenciário, permitindo o acompanhamento da frequência e das atividades desenvolvidas."""
    },
    3: {
        "cabeca": "Dona de lava-jato é condenada após polícia localizar carros roubados em estabelecimento de Natal",
        "off": """A 10ª Vara Criminal da Comarca de Natal condenou a proprietária de um lava-jato, localizado no bairro Bom Pastor, após a Polícia Civil localizar, no estabelecimento e na garagem da residência da denunciada, dois veículos com registro de roubo. A acusada alegou que os automóveis pertenciam a clientes, mas não soube identificar os proprietários nem apresentou qualquer registro dos veículos. A sentença, a concluiu que a mulher mantinha bens de origem ilícita em depósito no exercício de atividade comercial e, por esse motivo, aplicou penas restritivas de direitos.
Segundo denúncia do Ministério Público do RN, uma equipe da Polícia Civil rastreava uma caminhonete Toyota Hilux roubada na noite de 10 de julho de 2019 quando localizou o veículo no interior do lava-jato. Durante a fiscalização dos demais automóveis existentes no local, os policiais constataram que um Honda Fit também possuía registro de roubo. Os dois veículos foram apreendidos e a empresária presa em flagrante.
Os automóveis foram submetidos à perícia do Instituto Técnico-Científico de Perícia do RN e o laudo concluiu que ambos estavam sem as placas originais e possuíam registro de ocorrência por roubo.
Conduzida à Delegacia de Plantão, a acusada negou os fatos. Ela afirmou ser proprietária do lava-jato e alegou que os veículos pertenciam a clientes, mas disse não saber informar os nomes ou endereços das pessoas que os haviam deixado sob sua guarda."""
    },
    4: {
        "cabeca": "TJRN mantém decisão que afastou regressão de regime após rompimento de tornozeleira eletrônica",
        "off": """A Câmara Criminal do TJRN manteve a decisão que deixou de reconhecer falta grave de um apenado após o rompimento da tornozeleira eletrônica. O colegiado negou recurso do Ministério Público e entendeu que o descumprimento das condições do monitoramento, por si só, não justifica a regressão automática do regime de cumprimento da pena.
O recurso questionava decisão da 3ª Vara Regional de Execução Penal de Mossoró, que aplicou ao apenado a penalidade de advertência, sem reconhecer a prática de falta grave. Para o Ministério Público, o rompimento do equipamento, ocorrido em março de 2026, seria conduta equiparável à fuga.
O entendimento da Câmara, porém, foi diferente. Segundo o colegiado, embora o rompimento da tornozeleira represente descumprimento das condições impostas ao apenado, cada caso deve ser analisado individualmente, levando em consideração as circunstâncias em que o fato ocorreu.
Conforme o julgamento, pesaram a favor do apenado a comunicação espontânea do rompimento por sua defesa, a alegação de que o fato ocorreu durante un surto psicológico, a existência de documentação médica indicando transtorno afetivo bipolar, o pedido para reinstalação da tornozeleira e a ausência de indícios de fuga ou da prática de novo crime."""
    },
    5: {
        "cabeca": "Comitê Gestor de Penas Pecuniárias de Natal publica novo edital para cadastramento de projetos sociais",
        "off": """O Comitê Gestor de Penas Pecuniárias da Comarca de Natal publicou Edital , destinado ao cadastramento de entidades públicas ou privadas com finalidade social.
O valor total é de R$ 900 mil e será distribuído para 27 projetos que desenvolvam atividades de caráter essencial à segurança pública, educação e saúde, com predominância nas temáticas apresentadas no item 8 do Edital.
As inscrições devem ser feitas até o dia 30 de setembro, através do Aplicativo "Titina Social", desenvolvido pelo Tribunal de Justiça do Rio Grande do Norte, no endereço https://penaspecuniarias.tjrn.jus.br/login .
Na definição dos valores para cada projeto, foram consideradas informações contidas nas metas a serem cumpridas em 2026 pelo Grupo de Monitoramento e Fiscalização do Sistema Carcerário e de Execução das Medidas Socioeducativas do Tribunal de Justiça do RN, devidamente descritas no documento.
Os projetos inscritos e considerados aptos serão encaminhados ao Ministério Público para análise e, posteriormente, submetidos à apreciação do Comitê Gestor de Penas Pecuniárias da Comarca de Natal."""
    }
}


def normalizar(texto):
    """Normaliza texto para comparação."""
    import unicodedata
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def palavras_chave(texto):
    """Retorna conjunto de palavras-chave significativas."""
    stopwords = {"a", "o", "e", "de", "do", "da", "em", "um", "uma", "que", "para", "com", "por", "na", "no", "os", "as", "dos", "das", "se", "ao", "aos", "ou", "como", "mais", "mas", "ser", "foi", "sao", "tambem", "ate", "nao", "pelo", "pela", "seus", "sua", "suas", "dele", "dela", "entre", "sobre", "apos", "durante", "sem", "ja", "ainda", "quando", "cada", "mesmo", "bem", "onde", "isso", "este", "esta", "estas", "estes", "aquele", "aquela"}
    palavras = set(normalizar(texto).split())
    return palavras - stopwords


def similaridade_jaccard(texto1, texto2):
    """Similaridade de Jaccard entre dois textos."""
    p1 = palavras_chave(texto1)
    p2 = palavras_chave(texto2)
    if not p1 or not p2:
        return 0.0
    intersecao = p1 & p2
    uniao = p1 | p2
    return len(intersecao) / len(uniao)


def verificar_repeticoes(texto_boletim, texto_roteiro):
    """Verifica se há repetições no boletim que não estão no roteiro."""
    palavras_boletim = normalizar(texto_boletim).split()
    palavras_roteiro = set(normalizar(texto_roteiro).split())
    
    # Encontrar trechos repetidos
    problemas = []
    
    # Verificar se há frases repetidas
    frases = texto_boletim.split(". ")
    frases_repetidas = []
    for i, frase in enumerate(frases):
        frase_norm = normalizar(frase)
        if frase_norm in [normalizar(f) for f in frases[i+1:]]:
            if len(frase_norm.split()) > 3:  # Ignorar frases muito curtas
                frases_repetidas.append(frase[:80])
    
    return frases_repetidas


modelo = whisper.load_model("base")
pasta = Path("boletins/17 SET B1-B5_saida")

print("=" * 70)
print("AUDITORIA DOS BOLETINS 17/09")
print("=" * 70)

for n in range(1, 6):
    roteiro = ROTEIROS[n]
    boletim_file = pasta / f"BOLETIM_RADIO_TJRN_17_SET_2026_B{n}__{roteiro['cabeca'].upper()[:30]}.mp3"
    
    # Encontrar arquivo correto
    arquivos = list(pasta.glob(f"*B{n}__*.mp3"))
    if not arquivos:
        print(f"\n❌ B{n}: ARQUIVO NÃO ENCONTRADO")
        continue
    
    boletim_file = arquivos[0]
    print(f"\n{'='*70}")
    print(f"B{n}: {boletim_file.name[:60]}")
    print(f"{'='*70}")
    
    # Transcrever
    audio = AudioSegment.from_mp3(str(boletim_file))
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=None) as tmp:
        tmp_path = tmp.name
    audio.export(tmp_path, format="wav")
    result = modelo.transcribe(tmp_path, language="pt", fp16=False)
    os.unlink(tmp_path)
    
    texto_completo = " ".join(seg["text"] for seg in result["segments"])
    texto_norm = normalizar(texto_completo)
    
    # Verificar CABEÇA
    cabeca_norm = normalizar(roteiro["cabeca"])
    cabeca_palavras = palavras_chave(roteiro["cabeca"])
    texto_palavras = palavras_chave(texto_completo)
    cabeca_overlap = len(cabeca_palavras & texto_palavras) / len(cabeca_palavras) if cabeca_palavras else 0
    
    # Verificar OFF
    off_norm = normalizar(roteiro["off"])
    off_palavras = palavras_chave(roteiro["off"])
    off_overlap = len(off_palavras & texto_palavras) / len(off_palavras) if off_palavras else 0
    
    # Verificar repetições
    repeticoes = verificar_repeticoes(texto_completo, roteiro["off"])
    
    print(f"  Cabeça overlap: {cabeca_overlap:.1%}")
    print(f"  Off overlap:    {off_overlap:.1%}")
    
    if repeticoes:
        print(f"  ⚠ REPETIÇÕES ENCONTRADAS:")
        for r in repeticoes[:3]:
            print(f"    - \"{r}...\"")
    else:
        print(f"  ✓ Sem repetições detectadas")
    
    # Verificar palavras do roteiro que faltam no boletim
    palavras_faltando = off_palavras - texto_palavras
    if palavras_faltando:
        significativas = [p for p in palavras_faltando if len(p) > 4][:10]
        if significativas:
            print(f"  ⚠ Palavras do roteiro ausentes: {', '.join(significativas)}")
