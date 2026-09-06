#!/bin/bash
# Wrapper to run dispatcher in background, survives parent death
cd "E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
export PYTHONPATH="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/src"
exec python src/pipeline.dispatcher.py "E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/JORNAIS" "E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/data/processed/PRODUCAO_2026" --max-workers 1
