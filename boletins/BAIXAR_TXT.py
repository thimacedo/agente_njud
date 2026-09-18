import re
import urllib.request
from datetime import datetime

def extrair_ids_google_docs(texto_links):
    """Extrai IDs únicos de links do Google Docs."""
    regex = r'/d/([a-zA-Z0-9-_]+)'
    matches = re.findall(regex, texto_links)
    
    ids_unicos = []
    for doc_id in matches:
        if doc_id not in ids_unicos:
            ids_unicos.append(doc_id)
            
    return ids_unicos

def extrair_datas_do_texto(texto):
    """
    Busca datas nos formatos comum (DD/MM/AAAA) ou de nome de arquivo (DD_MM_AAAA).
    """
    # Regex para capturar DD/MM/AAAA ou DD_MM_AAAA
    padrao_data = r'\b(0[1-9]|[12][0-9]|3[01])[/_](0[1-9]|1[012])[/_](20\d\d)\b'
    matches = re.findall(padrao_data, texto)
    
    datas_encontradas = []
    for dia, mes, ano in matches:
        try:
            dt = datetime(int(ano), int(mes), int(dia))
            datas_encontradas.append(dt)
        except ValueError:
            continue
            
    return datas_encontradas

def unificar_google_docs():
    print("=" * 60)
    print("📄 EXTRATOR E UNIFICADOR DE GOOGLE DOCS (TXT)")
    print("=" * 60)
    print("Cole a lista de links abaixo (use Shift + Enter para quebras de linha).")
    print("Pressione ENTER em uma linha vazia quando terminar de colar:\n")

    linhas = []
    while True:
        try:
            linha = input()
            if not linha.strip() and len(linhas) > 0:
                break
            if linha.strip():
                linhas.append(linha)
        except EOFError:
            break

    texto_links = " ".join(linhas)
    ids = extrair_ids_google_docs(texto_links)

    if not ids:
        print("\n❌ Nenhum link válido do Google Docs foi identificado.")
        return

    print(f"\n📌 Encontrados {len(ids)} documentos únicos. Iniciando o download...\n")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    documentos_baixados = []
    todas_as_datas = []

    for i, doc_id in enumerate(ids, start=1):
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
        print(f"[{i}/{len(ids)}] Baixando documento ID: {doc_id}...")

        try:
            req = urllib.request.Request(export_url, headers=headers)
            with urllib.request.urlopen(req) as response:
                conteudo = response.read().decode('utf-8')

            # Extrai datas presentes no início ou ao longo do boletim
            datas_doc = extrair_datas_do_texto(conteudo)
            todas_as_datas.extend(datas_doc)

            documentos_baixados.append({
                "id": doc_id,
                "status": "OK",
                "conteudo": conteudo.strip()
            })

        except Exception as e:
            print(f"⚠️ Erro ao baixar o documento {doc_id}: {e}")
            documentos_baixados.append({
                "id": doc_id,
                "status": "ERRO",
                "conteudo": f"[ERRO AO EXTRAIR DOCUMENTO ID: {doc_id}]"
            })

    # Define o nome do arquivo com base na data mais recente encontrada nos boletins
    if todas_as_datas:
        data_mais_recente = max(todas_as_datas).strftime("%Y-%m-%d")
        print(f"\n📅 Data mais recente identificada nos boletins: {data_mais_recente}")
    else:
        data_mais_recente = datetime.now().strftime("%Y-%m-%d")
        print("\n⚠️ Nenhuma data identificada nos boletins. Utilizando a data atual.")

    nome_arquivo_saida = f"boletins_unificados_{data_mais_recente}.txt"

    # Salva o arquivo unificado
    with open(nome_arquivo_saida, "w", encoding="utf-8") as arquivo_txt:
        for i, doc in enumerate(documentos_baixados, start=1):
            arquivo_txt.write("=" * 50 + "\n")
            arquivo_txt.write(f"DOCUMENTO [{i}/{len(documentos_baixados)}] - ID: {doc['id']}\n")
            arquivo_txt.write("=" * 50 + "\n\n")
            arquivo_txt.write(doc['conteudo'] + "\n\n\n")

    print(f"\n✅ Concluído! Arquivo salvo como: {nome_arquivo_saida}")

if __name__ == "__main__":
    unificar_google_docs()