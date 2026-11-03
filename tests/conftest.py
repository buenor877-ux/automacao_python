import pytest

import automacoes
import banco


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    """Cada teste usa um banco e pastas novas e temporárias: o empresa.db real nunca é tocado."""
    monkeypatch.setattr(banco, "CAMINHO_DB", str(tmp_path / "teste.db"))
    monkeypatch.setattr(automacoes, "PASTA_BACKUPS", str(tmp_path / "backups"))
    monkeypatch.setattr(automacoes, "PASTA_RELATORIOS", str(tmp_path / "relatorios"))
    monkeypatch.setattr(automacoes, "ARQUIVO_CONFIG_EMAIL", str(tmp_path / "config_email.json"))
    banco.inicializar_banco()
    return tmp_path
