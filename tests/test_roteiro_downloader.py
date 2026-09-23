#!/usr/bin/env python3
"""
Testes para o AgenteRoteiroDownloader.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts_pipeline"))

from shared.agentes.roteiro_downloader import (
    extrair_ids,
    extrair_datas,
    extrair_metadados_roteiro,
    baixar_doc,
    salvar_roteiro_unificado,
    salvar_roteiros_individuais,
    processar_links,
)


class TestExtrairIds:
    def test_extrair_simples(self):
        texto = "https://docs.google.com/document/d/ABC123xyz/view"
        assert extrair_ids(texto) == ["ABC123xyz"]

    def test_extrair_multiplos(self):
        texto = (
            "https://docs.google.com/document/d/ID1abc/view\n"
            "https://docs.google.com/document/d/ID2def/edit\n"
            "https://docs.google.com/document/d/GHI789/"
        )
        assert extrair_ids(texto) == ["ID1abc", "ID2def", "GHI789"]

    def test_deduplica(self):
        texto = (
            "https://docs.google.com/document/d/SAME123/view "
            "https://docs.google.com/document/d/SAME123/edit"
        )
        assert extrair_ids(texto) == ["SAME123"]

    def test_sem_links(self):
        assert extrair_ids("texto sem links") == []

    def test_preserva_ordem(self):
        texto = (
            "https://docs.google.com/document/d/ZZZ/view "
            "https://docs.google.com/document/d/AAA/view "
            "https://docs.google.com/document/d/MMM/view"
        )
        assert extrair_ids(texto) == ["ZZZ", "AAA", "MMM"]

    def test_id_com_hifen(self):
        texto = "https://docs.google.com/document/d/abc-123_xyz/view"
        assert extrair_ids(texto) == ["abc-123_xyz"]


class TestExtrairDatas:
    def test_data_padrao(self):
        texto = "Data: 17/09/2026"
        datas = extrair_datas(texto)
        assert len(datas) == 1
        assert datas[0].year == 2026
        assert datas[0].month == 9
        assert datas[0].day == 17

    def test_data_com_underscore(self):
        texto = "roteiro_17_09_2026.txt"
        datas = extrair_datas(texto)
        assert len(datas) == 1
        assert datas[0].day == 17
        assert datas[0].month == 9
        assert datas[0].year == 2026

    def test_data_ano_2_digitos(self):
        texto = "Data: 17/09/26"
        datas = extrair_datas(texto)
        assert len(datas) == 1
        assert datas[0].year == 2026

    def test_sem_data(self):
        assert extrair_datas("texto sem data") == []

    def test_data_invalida(self):
        texto = "Data: 32/13/2026"
        assert extrair_datas(texto) == []

    def test_multiplas_datas(self):
        texto = "Início: 15/09/2026, Fim: 20/09/2026"
        datas = extrair_datas(texto)
        assert len(datas) == 2


class TestExtrairMetadados:
    def test_roteiro_completo(self):
        texto = (
            "B1- TJRN COMITÊ GESTOR\n"
            "CABEÇA: Comitê publica novo edital\n"
            "OFF:\n"
            "O Comitê Gestor publicou Edital..."
        )
        meta = extrair_metadados_roteiro(texto)
        assert len(meta["boletins"]) == 1
        assert meta["boletins"][0]["numero"] == 1
        assert "COMITÊ" in meta["boletins"][0]["titulo"]
        assert meta["boletins"][0]["cabeca"] == "Comitê publica novo edital"
        assert "O Comitê" in meta["boletins"][0]["off"]

    def test_roteiro_sem_off(self):
        texto = "B3- TJRN DONA LAVA-JATO CONDENADA"
        meta = extrair_metadados_roteiro(texto)
        assert len(meta["boletins"]) == 1
        assert meta["boletins"][0]["numero"] == 3
        assert meta["boletins"][0]["off"] == ""

    def test_multiplos_boletins(self):
        texto = (
            "B1- PRIMEIRA NOTÍCIA\n"
            "CABEÇA: Cabeça 1\n"
            "OFF: Texto 1\n\n"
            "B2- SEGUNDA NOTÍCIA\n"
            "CABEÇA: Cabeça 2\n"
            "OFF: Texto 2"
        )
        meta = extrair_metadados_roteiro(texto)
        assert len(meta["boletins"]) == 2
        assert meta["boletins"][0]["numero"] == 1
        assert meta["boletins"][1]["numero"] == 2

    def test_com_data(self):
        texto = "LEO-17/09/2026\nB1- TÍTULO"
        meta = extrair_metadados_roteiro(texto)
        assert meta["data"] is not None
        assert meta["data"].day == 17
        assert meta["data"].year == 2026

    def test_sem_boletins(self):
        texto = "Texto sem formato de boletim"
        meta = extrair_metadados_roteiro(texto)
        assert len(meta["boletins"]) == 0


class TestBaixarDoc:
    @patch("shared.agentes.roteiro_downloader.urllib.request.urlopen")
    def test_download_sucesso(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"Conteudo do roteiro"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        resultado = baixar_doc("test_id_123")
        assert resultado == "Conteudo do roteiro"

    @patch("shared.agentes.roteiro_downloader.urllib.request.urlopen")
    def test_download_remove_bom(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'\xef\xbb\xbfConteudo com BOM'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        resultado = baixar_doc("test_id")
        assert resultado == "Conteudo com BOM"

    @patch("shared.agentes.roteiro_downloader.urllib.request.urlopen")
    def test_download_falha_com_retry(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection error")
        
        with pytest.raises(Exception, match="Falha ao baixar"):
            baixar_doc("test_id")
        
        assert mock_urlopen.call_count == 3  # 3 retries


class TestSalvarRoteiroUnificado:
    def test_salva_arquivo(self, tmp_path):
        documentos = [
            {"id": "abc123", "status": "OK", "conteudo": "Roteiro 1\nB1- TÍTULO"},
            {"id": "def456", "status": "OK", "conteudo": "Roteiro 2\nB2- OUTRO"},
        ]
        
        path = salvar_roteiro_unificado(documentos, tmp_path)
        
        assert path.exists()
        assert path.suffix == ".txt"
        conteudo = path.read_text(encoding="utf-8")
        assert "Roteiro 1" in conteudo
        assert "Roteiro 2" in conteudo
        assert "DOCUMENTO [1/2]" in conteudo
        assert "DOCUMENTO [2/2]" in conteudo

    def test_com_data_no_nome(self, tmp_path):
        documentos = [
            {"id": "abc", "status": "OK", "conteudo": "Data: 20/09/2026\nB1- TÍTULO"},
        ]
        
        path = salvar_roteiro_unificado(documentos, tmp_path)
        
        assert "2026-09-20" in path.name

    def test_sem_data_fallback(self, tmp_path):
        documentos = [
            {"id": "abc", "status": "OK", "conteudo": "Sem data no texto"},
        ]
        
        path = salvar_roteiro_unificado(documentos, tmp_path)
        
        assert "roteiros_" in path.name
        assert path.suffix == ".txt"

    def test_com_erro(self, tmp_path):
        documentos = [
            {"id": "ok", "status": "OK", "conteudo": "OK"},
            {"id": "fail", "status": "ERRO", "conteudo": ""},
        ]
        
        path = salvar_roteiro_unificado(documentos, tmp_path)
        conteudo = path.read_text(encoding="utf-8")
        
        assert "ERRO" in conteudo
        assert "fail" in conteudo


class TestSalvarRoteirosIndividuais:
    def test_salva_individuais(self, tmp_path):
        documentos = [
            {
                "id": "abc",
                "status": "OK",
                "conteudo": "B1- TÍTULO A\nCABEÇA: Cabeça A\nOFF: Texto A"
            },
            {
                "id": "def",
                "status": "OK",
                "conteudo": "B2- TÍTULO B\nCABEÇA: Cabeça B\nOFF: Texto B"
            },
        ]
        
        paths = salvar_roteiros_individuais(documentos, tmp_path)
        
        assert len(paths) == 2
        assert all(p.exists() for p in paths)

    def test_ignora_erros(self, tmp_path):
        documentos = [
            {"id": "ok", "status": "OK", "conteudo": "B1- TÍTULO\nOFF: Texto"},
            {"id": "fail", "status": "ERRO", "conteudo": ""},
        ]
        
        paths = salvar_roteiros_individuais(documentos, tmp_path)
        
        assert len(paths) == 1


class TestProcessarLinks:
    @patch("shared.agentes.roteiro_downloader.baixar_doc")
    def test_processar_sucesso(self, mock_baixar, tmp_path):
        mock_baixar.return_value = "B1- TÍTULO TESTE\nCABEÇA: Teste\nOFF: Conteúdo"
        
        links = "https://docs.google.com/document/d/DOC123/view"
        resultado = processar_links(links, tmp_path)
        
        assert resultado["status"] == "sucesso"
        assert resultado["estatisticas"]["sucesso"] == 1
        assert len(resultado["arquivos_criados"]) == 1

    @patch("shared.agentes.roteiro_downloader.baixar_doc")
    def test_processar_sem_links(self, mock_baixar, tmp_path):
        resultado = processar_links("texto sem links", tmp_path)
        
        assert resultado["status"] == "erro"
        assert resultado["estatisticas"]["total"] == 0

    @patch("shared.agentes.roteiro_downloader.baixar_doc")
    def test_processar_parcial(self, mock_baixar, tmp_path):
        def side_effect(doc_id):
            if doc_id == "OK1":
                return "B1- TÍTULO"
            raise Exception("Falha")
        
        mock_baixar.side_effect = side_effect
        
        links = (
            "https://docs.google.com/document/d/OK1/view "
            "https://docs.google.com/document/d/FAIL/view"
        )
        resultado = processar_links(links, tmp_path)
        
        assert resultado["status"] == "parcial"
        assert resultado["estatisticas"]["sucesso"] == 1
        assert resultado["estatisticas"]["falha"] == 1

    @patch("shared.agentes.roteiro_downloader.baixar_doc")
    def test_modo_individual(self, mock_baixar, tmp_path):
        mock_baixar.return_value = "B1- TÍTULO A\nOFF: Texto A\n\nB2- TÍTULO B\nOFF: Texto B"
        
        links = "https://docs.google.com/document/d/DOC1/view"
        resultado = processar_links(links, tmp_path, modo="individual")
        
        assert resultado["status"] == "sucesso"
        assert len(resultado["arquivos_criados"]) == 2  # 2 boletins
