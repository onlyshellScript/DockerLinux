# Catálogo de materiales para gas natural

## Criterios de clasificación

- Materiales organizados por categoría técnica, sin dimensiones ni certificaciones inventadas.

- Nombres en español con acentos correctos; `name_norm` calculado con `normalize_text()` (minúsculas, sin acentos, espacios colapsados).

- Códigos secuenciales `GAS-001`..`GAS-166`, únicos.

- Unidades: m (tubería), pza (accesorios/equipos), rollo/kg (cintas/mallas/arena), lt/kg (selladores/pastas).

- Etapas: Instalación, Medición, Regulación, Seguridad, Señalización.

- `applies_to`: todos, industrial (soldadura).


## Fuentes consultadas

- Práctica técnica general de instalación de redes de gas natural; denominaciones comerciales estándar en español.

- No se inventaron especificaciones, dimensiones ni certificaciones.


## Categorías y conteos

- Tuberia: 15
- Accesorios de tuberia: 25
- Valvulas: 15
- Medicion: 10
- Regulacion: 10
- Conexiones y empalmes: 15
- Proteccion y seguridad: 12
- Soportes y fijacion: 10
- Materiales de instalacion y sellado: 15
- Soldadura y union: 12
- Senalizacion e identificacion: 8
- Equipos y herramientas: 12
- Proteccion personal: 7

Total: 166


## Advertencias

- Catálogo base para revisión humana; validar denominaciones con proveedores locales.

- Algunos elementos (soldadura) marcados applies_to=industrial.

- Unidades sin decimales en inventario rechazan fracciones; tubería en metros puede requerir decimales en movimientos (cantidad > 0).
