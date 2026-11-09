# AnonDoc Benchmark Suite (Fase 0)

Este directorio contiene el arnés de evaluación científica y el dataset de referencia para medir con rigor cuantitativo el rendimiento de los detectores de PII en AnonDoc.

## 1. Estructura de archivos

- `build_dataset.py`: Generador y validador de integridad del dataset. Garantiza que cada entidad anotada coincide exactamente carácter por carácter (`text[start_char:end_char] == item["text"]`) y que no existen solapamientos en la verdad de referencia (*ground truth*).
- `dataset.jsonl`: Archivo de datos estandarizado en formato JSONL con documentos y anotaciones exactas.
- `run_benchmark.py`: Arnés ejecutable que corre cualquier implementación de `IPIIDetector` contra el dataset y calcula Precision, Recall, F1, Falsos Positivos, Falsos Negativos, latencia y consumo de memoria (RSS).
- `baseline_results.json`: Registro congelado de la medición basal del motor v2.0 determinista actual, utilizado para pruebas de regresión.

## 2. Procedencia y diseño del dataset

El dataset contiene documentos administrativos, judiciales, de salud, laborales y municipales contextualizados en el ámbito hispanohablante y ecuatoriano, además de controles negativos explícitos:

1. **Documentos judiciales y notariales:** Actas de comparecencia, demandas laborales y poderes especiales.
2. **Documentos clínicos y médicos:** Epicrisis cardiológicas y certificados oncológicos.
3. **Documentos laborales y de RRHH:** Roles individuales de pago de haberes y contratos de servicios profesionales.
4. **Documentos municipales y de tránsito:** Citaciones por infracción vehicular y licencias metropolitanas de construcción.
5. **Documentos financieros y telemáticos:** Solicitudes de crédito con tarjetas y reportes de incidentes CSIRT.
6. **Controles negativos (trampas de falsos positivos):**
   - Textos normativos saturados de mayúsculas (nombres de leyes, códigos orgánicos, instituciones públicas como *"Asamblea Nacional"*, *"Corte Constitucional"*, *"Defensoría del Pueblo"*).
   - Registros de metadatos con códigos numéricos que no son cédulas ni teléfonos válidos.
7. **Desafíos semánticos:** Comparecencias con nombres en minúsculas accidentales o sin tratamientos honoríficos (`Mateo Sebastián Morales de la Torre`, `Andrea Belén del Pozo Carrión`).

## 3. Criterios de anotación y resolución de discrepancias

- **Identificadores directos:** Se anotan con sus límites exactos (`start_char`, `end_char`).
- **Nombres propios (`PERSON`):** Se anota el nombre completo excluyendo tratamientos honoríficos (*Sr.*, *Dr.*, *Abg.*) salvo que formen parte inseparable del texto de la entidad según la categoría.
- **Direcciones (`ADDRESS`):** Se anota la expresión geográfica o vial completa.
- **Ausencia de solapamientos en Ground Truth:** Si una entidad aparece dentro de otra (ej. una ciudad dentro de una dirección), se anota la entidad de mayor especificidad contextual para evitar ambigüedades en la evaluación estricta.

## 4. Ejecución del benchmark

Para ejecutar la evaluación y contrastar contra la línea base:

```bash
PYTHONPATH=. .venv/bin/python tests/benchmark/run_benchmark.py
```
