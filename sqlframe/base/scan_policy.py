from __future__ import annotations

import typing as t
from collections.abc import Mapping

from sqlglot import exp, parse_one
from sqlglot.dialects.dialect import Dialect, DialectType
from sqlglot.schema import normalize_name


class ScanPolicy:
    """Per-table row predicates to apply when a listed table is read.

    Tables are named as ``table`` or ``db.table`` / ``catalog.db.table``.
    Predicates are SQL boolean expressions in the session's input dialect,
    evaluated against columns of that table only (for example ``tenant_id = 1``).

    Identifier comparison uses the same dialect normalization as schema names.
    """

    def __init__(
        self,
        predicates: Mapping[str, str] | None = None,
        dialect: DialectType = None,
    ) -> None:
        self._dialect: Dialect = Dialect.get_or_raise(dialect)
        self._entries: dict[tuple[str, ...], str] = {}
        if predicates:
            for table, predicate in predicates.items():
                self.add(table, predicate)

    @property
    def dialect(self) -> Dialect:
        return self._dialect

    def add(self, table: str, predicate: str, dialect: DialectType = None) -> ScanPolicy:
        parts = self._normalize_table_parts(table, dialect=dialect)
        if not parts:
            raise ValueError(f"Scan policy table names must be non-empty, got: {table!r}")
        pred = (predicate or "").strip()
        if not pred:
            raise ValueError(f"Scan policy predicate for {table!r} must be non-empty")
        self._entries[parts] = pred
        return self

    def predicate_sql(self, table: str | exp.Table, dialect: DialectType = None) -> str | None:
        """Return the predicate SQL for ``table``, or None if it is not listed."""
        parts = self._normalize_table_parts(table, dialect=dialect)
        if not parts:
            return None
        for key, pred in self._entries.items():
            overlap = min(len(key), len(parts))
            if overlap >= 1 and key[-overlap:] == parts[-overlap:]:
                return pred
        return None

    def predicate_expr(
        self, table: str | exp.Table, dialect: DialectType = None
    ) -> exp.Expr | None:
        sql = self.predicate_sql(table, dialect=dialect)
        if sql is None:
            return None
        dialect = dialect if dialect is not None else self._dialect
        return parse_one(sql, dialect=dialect)

    def _normalize_table_parts(
        self, table: str | exp.Table, dialect: DialectType = None
    ) -> tuple[str, ...]:
        dialect = dialect if dialect is not None else self._dialect
        if isinstance(table, exp.Table):
            pieces = [p for p in (table.catalog, table.db, table.name) if p]
            return tuple(normalize_name(p, dialect=dialect) for p in pieces)
        text = str(table).strip()
        if not text:
            return ()
        pieces = [p for p in text.split(".") if p]
        return tuple(normalize_name(p, dialect=dialect) for p in pieces)
