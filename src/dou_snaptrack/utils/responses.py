"""
Padrões de resposta para comunicação entre processos e APIs.

Este módulo centraliza o formato de respostas JSON para garantir consistência
em todo o projeto, especialmente em comunicação subprocess ↔ UI.

Exemplo:
    >>> result = OperationResult.ok({"items": [1, 2, 3]})
    >>> print(result.to_json())
    {"success": true, "data": {"items": [1, 2, 3]}}

    >>> result = OperationResult.fail("Conexão timeout")
    >>> print(result.to_json())
    {"success": false, "error": "Conexão timeout"}
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class OperationResult:
    """
    Resultado padronizado para operações.

    Attributes:
        success: Se a operação foi bem sucedida.
        data: Dados retornados (quando success=True).
        error: Mensagem de erro (quando success=False).
        metadata: Informações adicionais opcionais (timing, contagens, etc).
    """

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self, ensure_ascii: bool = False) -> str:
        """Serializa para JSON string."""
        d = {"success": self.success}
        if self.success:
            if self.data is not None:
                d["data"] = self.data
        else:
            if self.error:
                d["error"] = self.error
        if self.metadata:
            d["metadata"] = self.metadata
        return json.dumps(d, ensure_ascii=ensure_ascii)

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário."""
        return asdict(self)

    @classmethod
    def ok(cls, data: Any = None, **metadata: Any) -> OperationResult:
        """
        Cria resultado de sucesso.

        Args:
            data: Dados a retornar.
            **metadata: Metadados adicionais (ex: elapsed_ms=150).
        """
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata: Any) -> OperationResult:
        """
        Cria resultado de falha.

        Args:
            error: Mensagem de erro.
            **metadata: Metadados adicionais.
        """
        return cls(success=False, error=error, metadata=metadata)

    @classmethod
    def from_json(cls, json_str: str) -> OperationResult:
        """
        Deserializa de JSON string.

        Args:
            json_str: String JSON no formato esperado.

        Returns:
            OperationResult reconstruído.

        Raises:
            json.JSONDecodeError: Se JSON inválido.
        """
        d = json.loads(json_str)
        return cls(
            success=d.get("success", False),
            data=d.get("data"),
            error=d.get("error"),
            metadata=d.get("metadata", {}),
        )


@dataclass
class FetchResult(OperationResult):
    """
    Resultado específico para operações de fetch (dropdowns, listas).

    Extends OperationResult com campos específicos para coleta de dados.
    """

    @classmethod
    def ok_with_options(
        cls,
        n1_options: list[str],
        n2_mapping: dict[str, list[str]] | None = None,
        **metadata: Any,
    ) -> FetchResult:
        """
        Cria resultado de sucesso para fetch de opções.

        Args:
            n1_options: Lista de opções de nível 1 (órgãos).
            n2_mapping: Mapeamento N1 → lista de N2 (opcional).
            **metadata: Metadados adicionais.
        """
        data = {"n1_options": n1_options}
        if n2_mapping is not None:
            data["n2_mapping"] = n2_mapping
        return cls(success=True, data=data, metadata=metadata)


@dataclass
class BatchResult(OperationResult):
    """
    Resultado específico para operações em lote.
    """

    @classmethod
    def ok_with_stats(
        cls,
        total: int,
        success_count: int,
        failed_count: int,
        items: list[Any] | None = None,
        **metadata: Any,
    ) -> BatchResult:
        """
        Cria resultado de sucesso para operação em lote.

        Args:
            total: Total de itens processados.
            success_count: Quantidade de sucessos.
            failed_count: Quantidade de falhas.
            items: Lista de resultados individuais (opcional).
            **metadata: Metadados adicionais.
        """
        data = {
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
        }
        if items is not None:
            data["items"] = items
        return cls(success=True, data=data, metadata=metadata)


# =============================================================================
# Funções utilitárias para compatibilidade com código existente
# =============================================================================


def success_response(data: Any = None, **kwargs: Any) -> str:
    """
    Helper para criar resposta JSON de sucesso.

    Compatível com o padrão existente de print(json.dumps({...})).
    """
    return OperationResult.ok(data, **kwargs).to_json()


def error_response(error: str, **kwargs: Any) -> str:
    """
    Helper para criar resposta JSON de erro.

    Compatível com o padrão existente de print(json.dumps({...})).
    """
    return OperationResult.fail(error, **kwargs).to_json()


def parse_subprocess_output(output: str) -> OperationResult:
    """
    Extrai e parseia a última linha JSON de saída de subprocess.

    Ignora linhas de log e warnings, buscando apenas JSON válido.

    Args:
        output: Saída completa do subprocess.

    Returns:
        OperationResult parseado ou erro se não encontrar JSON.
    """
    lines = output.strip().splitlines()

    # Procura de trás para frente pela última linha JSON
    for line in reversed(lines):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return OperationResult.from_json(line)
            except json.JSONDecodeError:
                continue

    return OperationResult.fail(f"Nenhum JSON válido encontrado na saída: {output[:200]}")
