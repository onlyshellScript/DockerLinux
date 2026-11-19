"""Motor centralizado de exportaciones (PDF / XLSX) basado en plantillas declarativas.

Capas:
  templates.py  -> definicion de plantillas (que se exporta y como se presenta)
  sources.py    -> obtencion y normalizacion de datos reutilizando los servicios de cada modulo
  engine.py     -> seleccion de plantilla, configuracion, dataset, hash, validacion y nombre de archivo
  render_pdf.py -> renderizado PDF institucional (reportlab)
  render_xlsx.py-> renderizado XLSX con tipos reales (openpyxl)
  routes.py     -> API: catalogo, vista previa y generacion
"""
