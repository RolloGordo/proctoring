"""Cliente de Supabase de mentira.

Reproduce lo justo de la interfaz encadenada de PostgREST que usan nuestros
adaptadores: `client.table(t).select(c).eq(k, v).limit(n).order(c).execute()` y
`client.table(t).insert(row).execute()`.

Es un doble, no un emulador: no valida tipos ni restricciones de PostgreSQL. Lo
que prueba es **nuestro codigo** — que mandemos los nombres de columna correctos,
que filtremos y ordenemos por lo que toca, y que la traduccion fila <-> entidad
sea de ida y vuelta.
"""

from __future__ import annotations

from typing import Any


class FakeResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class FakeTable:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows: list[dict[str, Any]] = [dict(row) for row in (rows or [])]
        #: Lo insertado, para comprobar la forma exacta de la fila.
        self.inserted: list[dict[str, Any]] = []
        #: Cuantas consultas de lectura recibio, para comprobar las caches.
        self.select_count = 0
        #: Las columnas que se pidieron en el ultimo select.
        self.selected_columns: str | None = None


class FakeQueryBuilder:
    def __init__(self, table: FakeTable) -> None:
        self._table = table
        self._filters: list[tuple[str, Any]] = []
        self._order: str | None = None
        self._desc = False
        self._limit: int | None = None
        self._insert: dict[str, Any] | None = None

    def select(self, columns: str = "*") -> FakeQueryBuilder:
        self._table.selected_columns = columns
        return self

    def insert(self, row: dict[str, Any]) -> FakeQueryBuilder:
        self._insert = row
        return self

    def eq(self, column: str, value: Any) -> FakeQueryBuilder:
        self._filters.append((column, value))
        return self

    def limit(self, count: int) -> FakeQueryBuilder:
        self._limit = count
        return self

    def order(self, column: str, desc: bool = False) -> FakeQueryBuilder:
        self._order = column
        self._desc = desc
        return self

    def execute(self) -> FakeResponse:
        if self._insert is not None:
            self._table.rows.append(dict(self._insert))
            self._table.inserted.append(dict(self._insert))
            return FakeResponse([dict(self._insert)])

        self._table.select_count += 1
        rows = [
            row
            for row in self._table.rows
            # PostgREST compara en texto por la URL, asi que el doble hace lo mismo.
            if all(str(row.get(column)) == str(value) for column, value in self._filters)
        ]
        if self._order is not None:
            column = self._order
            rows = sorted(rows, key=lambda row: str(row[column]), reverse=self._desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return FakeResponse([dict(row) for row in rows])


class FakeSupabaseClient:
    """Sustituye a `supabase.Client` en las pruebas."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.tables: dict[str, FakeTable] = {
            name: FakeTable(rows) for name, rows in (tables or {}).items()
        }

    def table(self, name: str) -> FakeQueryBuilder:
        if name not in self.tables:
            self.tables[name] = FakeTable()
        return FakeQueryBuilder(self.tables[name])
