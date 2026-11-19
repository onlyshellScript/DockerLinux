# Migraciones históricas (esquema en inglés)

Cadena original `683fd21c4219` … `e2a3b4c5d6e7` (21 revisiones), que creaba tablas con nombres en inglés
(`users`, `work_orders`, …). **No forma parte del árbol activo de Alembic**: Alembic solo lee `../versions/`.

- Los modelos actuales usan el esquema en español creado por `versions/ef3ab0606ef4` (baseline); una base creada con
  esta cadena no es compatible con el código actual.
- `d4e5f6a7b8c9` se recuperó de `versions_backup/` (nunca había estado en Git); con ella la cadena está completa.
- Se conserva como referencia histórica. **No volver a copiar estos archivos a `versions/`**: crearía una segunda raíz.

Detalle: `docs/architecture/migration-recovery-plan.md`.
