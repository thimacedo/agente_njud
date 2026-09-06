from pathlib import Path
import json
import sys


def gerar_relatorio_audit(caminho_audit: Path):
    if not caminho_audit.exists():
        print(f"Arquivo não encontrado: {caminho_audit}")
        return

    with open(caminho_audit, "r", encoding="utf-8") as f:
        dados = json.load(f)

    total = dados.get("total_arquivos", 0)
    processados = dados.get("processados", 0)
    erros = dados.get("erros", 0)

    print("=" * 60)
    print("RELATÓRIO DE AUDITORIA — DIVISOR DE BOLETINS")
    print("=" * 60)
    print(f"Total de arquivos: {total}")
    print(f"Processados: {processados}")
    print(f"Erros: {erros}")
    print()

    contagem = dados.get("contagem_metodos", {})
    if contagem:
        print("Contagem por método:")
        for metodo, qtd in sorted(contagem.items()):
            pct = (qtd / processados * 100) if processados else 0
            print(f"  {metodo}: {qtd} ({pct:.1f}%)")
    else:
        print("Sem contagem de métodos no AUDIT.")

    print()
    print("Primeiros resultados:")
    for i, r in enumerate(dados.get("resultados", [])[:10], 1):
        print(
            f"  {i:02d}. {r.get('arquivo_entrada', '?')} | "
            f"método={r.get('metodo', '?')} | "
            f"abertura={r.get('metodo_abertura', '?')} | "
            f"passagem={r.get('metodo_passagem', '?')} | "
            f"encerramento={r.get('metodo_encerramento', '?')}"
        )

    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python relatorio_audit.py <caminho_para_AUDIT_cortes.json>")
        sys.exit(1)
    gerar_relatorio_audit(Path(sys.argv[1]))
