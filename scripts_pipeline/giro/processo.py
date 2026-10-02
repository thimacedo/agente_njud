"""Interface canônica GIRO: planejar, validar, montar e sincronizar separadamente."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from giro.controle_producao import (
    carregar_json_giro, montar_manifesto_giro, planejar_giro, raiz_giro,
    salvar_json_giro, sincronizar_giro, validar_manifesto_giro,
    validar_edicao_giro,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz', type=Path, default=raiz_giro())
    sub = parser.add_subparsers(dest='acao', required=True)
    p = sub.add_parser('planejar', help='Somente leitura; imprime JSON para revisão')
    p.add_argument('--ano', type=int, required=True)
    p.add_argument('--mes', type=int, required=True)
    p.add_argument('--fonte', type=Path, action='append')
    p.add_argument('--salvar', type=Path, help='Salvar explicitamente o relatório, sem sobrescrever')
    p = sub.add_parser('manifesto', help='Extrai rascunho editorial de uma edição do planejamento')
    p.add_argument('planejamento', type=Path)
    p.add_argument('--codigo', required=True)
    p.add_argument('--salvar', type=Path)
    p = sub.add_parser('validar', help='Valida manifesto, evidências, hashes e durações')
    p.add_argument('manifesto', type=Path)
    p = sub.add_parser('montar', help='Gera candidato local; não sincroniza')
    p.add_argument('manifesto', type=Path)
    p.add_argument('--apply', action='store_true', help='Autoriza gerar uma nova versão local')
    p = sub.add_parser('sync', help='Sincroniza somente o candidato com revisão final')
    p.add_argument('candidato', type=Path)
    p.add_argument('--revisao', type=Path, required=True)
    p.add_argument('--destino', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        raiz = args.raiz.resolve()
        if args.acao == 'planejar':
            fontes = args.fonte or [raiz / 'GIRO/input', raiz / 'setembro']
            relatorio = planejar_giro(args.ano, args.mes, fontes, raiz)
            if args.salvar:
                if args.salvar.resolve().suffix.lower() != '.json':
                    raise ValueError('Relatório deve usar extensão .json')
                salvar_json_giro(args.salvar, relatorio)
            print(json.dumps(relatorio, ensure_ascii=False, indent=2))
        elif args.acao == 'validar' or (args.acao == 'montar' and not args.apply):
            manifesto = args.manifesto.resolve()
            validar_manifesto_giro(carregar_json_giro(manifesto), manifesto.parent, raiz, permitir_montagem_local_autorizada=args.acao == 'montar')
            print('Manifesto válido. Nenhum áudio produzido.')
        elif args.acao == 'manifesto':
            plano = carregar_json_giro(args.planejamento)
            edicao = next((e for e in plano['edicoes'] if e['codigo'] == args.codigo), None)
            if edicao is None:
                raise ValueError('Edição não encontrada no planejamento')
            validar_edicao_giro(edicao)
            if args.salvar:
                salvar_json_giro(args.salvar, edicao)
            print(json.dumps(edicao, ensure_ascii=False, indent=2))
        elif args.acao == 'montar':
            print(montar_manifesto_giro(args.manifesto, raiz))
        elif args.acao == 'sync':
            if not args.apply:
                raise ValueError('Sync exige --apply, candidato e revisão final explícitos')
            print(sincronizar_giro(args.candidato, args.revisao, args.destino, raiz))
        return 0
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as exc:
        print(f'GIRO interrompido: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

