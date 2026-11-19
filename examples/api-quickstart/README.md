# Ejemplo: cliente mínimo de la API SIGOS 2.0

Requiere el backend ejecutándose en `http://localhost:5000`.

## Ejecutar

```powershell
cd examples/api-quickstart
python main.py
```

## Resultado esperado

```text
Health: {'checks': {'application': 'UP', 'database': 'UP'}, 'status': 'UP'}
Orden creada: <id> pending
```

Sin dependencias externas (solo biblioteca estándar de Python).
