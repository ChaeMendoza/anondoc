# AnonDoc 🛡️

**Motor Independiente de Detección y Anonimización de Información Personal en Documentos PDF y DOCX.**

AnonDoc es una aplicación web y API REST diseñada para que cualquier persona u organización pueda cargar documentos, identificar automáticamente información personal y sensible (PII), revisar los hallazgos en una interfaz con control humano (*Human-in-the-Loop*) y generar documentos anonimizados de forma irreversible y segura.

---

## 📌 Tabla de Contenidos
1. [Características Principales](#-características-principales)
2. [Arquitectura del Sistema (Clean Architecture)](#-arquitectura-del-sistema)
3. [Motor de Detección Híbrida PII](#-motor-de-detección-híbrida-pii)
4. [Estrategias de Anonimización](#-estrategias-de-anonimización)
5. [Seguridad y Privacidad por Diseño](#-seguridad-y-privacidad-por-diseño)
6. [Requisitos Previos e Instalación](#-requisitos-previos-e-instalación)
7. [Ejecución en Desarrollo](#-ejecución-en-desarrollo)
8. [Ejecución mediante Docker](#-ejecución-mediante-docker)
9. [Especificación de la API REST](#-especificación-de-la-api-rest)
10. [Pruebas Automatizadas](#-pruebas-automatizadas)
11. [Limitaciones Conocidas](#-limitaciones-conocidas)

---

## 🌟 Características Principales

- **Procesamiento 100% Local y Privado:** No envía documentos ni datos a proveedores en la nube o LLMs externos. Todo el análisis se ejecuta en el servidor.
- **Redacción Nativa Irreversible en PDF:** A diferencia de visores que colocan rectángulos negros sobre el texto, AnonDoc utiliza las corrientes de redacción nativas de PyMuPDF, eliminando físicamente los objetos de texto y caracteres del PDF.
- **Anonimización Estructural en DOCX:** Recorre párrafos, tablas, encabezados, pies de página y limpia los metadatos *core* del documento (autores, comentarios, revisiones).
- **Enfoque Human-in-the-Loop:** Interfaz web minimalista y moderna que permite activar/desactivar detecciones, corregir falsos positivos y añadir datos manualmente antes de compilar el archivo definitivo.
- **Múltiples Estrategias:** Soporta Redacción (`[DATO ANONIMIZADO]`), Seudonimización consistente (`PERSONA_001`, `CEDULA_001`) y Enmascaramiento (`u*****@correo.com`, `********05`).

---

## 🏗 Arquitectura del Sistema

AnonDoc está construido bajo los principios de **Clean Architecture**, asegurando que las reglas de negocio y los motores de procesamiento estén completamente desacoplados del framework web:

```mermaid
flowchart TD
    subgraph Presentation ["Presentation Layer"]
        UI["Interfaz Web (HTML5/CSS3/Vanilla JS)"]
        API["FastAPI REST Endpoints (/api/v1)"]
    end

    subgraph Application ["Application Layer"]
        UC["Use Cases (Upload, Analyze, Anonymize, Download)"]
        JM["JobManager (Sesiones Epímeras en Memoria)"]
    end

    subgraph Domain ["Domain Layer (Pure Business Rules)"]
        Entities["PIIEntity, DocumentJob, Enums"]
        Validators["Algoritmos (Módulo 10 Cédula, RUC, Luhn, IPv4)"]
        Interfaces["IDocumentExtractor, IPIIDetector, IDocumentAnonymizer"]
    end

    subgraph Infrastructure ["Infrastructure Layer"]
        PDF["PDFEngine (PyMuPDF Native Redaction)"]
        DOCX["DOCXEngine (python-docx Surgical Run Replacement)"]
        Detector["HybridPIIDetector (Regex + Algoritmos + Context)"]
        Storage["SecureStorageService (Magic Bytes, Zip Bomb, Purge)"]
    end

    Presentation --> Application
    Application --> Domain
    Application --> Infrastructure
    Infrastructure --> Domain
```

---

## 🔍 Motor de Detección Híbrida PII

AnonDoc combina tres capas complementarias para garantizar una alta precisión y minimizar falsos positivos:

1. **Reconocimiento de Patrones y Regex:** Identificación de correos, teléfonos, placas, IPs, etc.
2. **Validación Algorítmica Determinista:**
   - **Cédulas Ecuatorianas:** Validación matemática de provincia (01-24, 30), tercer dígito (< 6) y dígito verificador mediante algoritmo módulo 10.
   - **RUC Ecuatoriano:** Validación de personas naturales (10 dígitos + 001), sociedades privadas (tercer dígito 9, módulo 11) e instituciones públicas (tercer dígito 6, módulo 11).
   - **Tarjetas Bancarias:** Validación de tarjetas Visa, Mastercard, Amex, Diners mediante el algoritmo de Luhn.
   - **Direcciones IPv4:** Validación de rangos numéricos de octetos (0-255).
3. **Análisis de Contexto Lingüístico:**
   - Filtro de frases institucionales comunes para evitar clasificar nombres de leyes, entidades públicas o fechas como personas.
   - Detección de títulos personales (`Dr.`, `Ing.`, `Abg.`, `Sr.`, `compareciente`) para elevar la confianza de nombres propios.

### Niveles de Confianza
- **ALTA (`HIGH`):** Superó validación matemática estricta (ej. Cédula válida, email RFC, tarjeta Luhn).
- **MEDIA (`MEDIUM`):** Coincidencia regex con palabras clave de contexto cercanas (ej. "teléfono: 098...").
- **BAJA (`LOW`):** Coincidencia léxica ambigua. Se presenta al usuario para revisión obligatoria y no se anonimiza silenciosamente.

---

## 🎭 Estrategias de Anonimización

| Estrategia | Descripción | Ejemplo de Entrada | Resultado |
| :--- | :--- | :--- | :--- |
| **Redacción** | Sustituye el texto por etiquetas descriptivas fijas o personalizadas. | `0102030405` | `[CEDULA_ANONIMIZADO]` |
| **Seudonimización** | Asigna identificadores consistentes para cada entidad a lo largo del documento. | `Carlos Pérez` ... `Carlos Pérez` | `PERSONA_001` ... `PERSONA_001` |
| **Enmascaramiento** | Oculta parcialmente los datos conservando los últimos dígitos o iniciales. | `juan@empresa.com`<br>`0987654321` | `j***@empresa.com`<br>`******4321` |

---

## 🔒 Seguridad y Privacidad por Diseño

- **Aislamiento de Trabajos:** Cada documento se procesa en una carpeta temporal dedicada identificada por un UUIDv4 criptográficamente seguro.
- **Protección contra Path Traversal:** Verificación estricta de rutas con `commonpath` para impedir manipulación de directorios.
- **Inspección de Magic Bytes:** Validación real de cabeceras de archivo (`%PDF-` y `PK\x03\x04`). Los archivos maliciosos renombrados son rechazados antes de ser parseados.
- **Protección contra Zip Bombs:** Inspección del contenedor ZIP de archivos DOCX con límite de tamaño no comprimido y límite de ratio de descompresión.
- **Eliminación Automática (Auto-purge):** Archivos temporales con TTL de 30 minutos (configurable).
- **Cero Telemetría y Logs Limpios:** No se imprime texto de los documentos ni valores de PII en la consola ni en logs de auditoría.
- **Verificación Residual:** Tras redactar un PDF o DOCX, el motor ejecuta una pasada de verificación automática para asegurar que el texto original no pueda ser extraído ni buscado.

---

## 📦 Requisitos Previos e Instalación

### Requisitos del Sistema
- **Python:** 3.11 o 3.12.
- **LibreOffice:** (Opcional, utilizado para conversiones de formatos heredados).

### Instalación Local
```bash
# 1. Clonar el repositorio
git clone https://github.com/ChaeMendoza/anondoc.git
cd anondoc

# 2. Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## 🚀 Ejecución en Desarrollo

Para iniciar la aplicación web y la API REST:
```bash
python -m anondoc.main
```
La aplicación estará disponible de inmediato en:
- **Interfaz Web (Dashboard):** [http://localhost:8000](http://localhost:8000)
- **Documentación Interactiva (Swagger/OpenAPI):** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🐳 Ejecución mediante Docker

AnonDoc cuenta con soporte para Docker y Docker Compose sin requerir configuraciones adicionales:

```bash
# Construir e iniciar el contenedor
docker compose up -d --build

# Ver logs de la aplicación
docker compose logs -f

# Detener el contenedor
docker compose down
```

---

## 📡 Especificación de la API REST

Todos los endpoints se encuentran versionados bajo el prefijo `/api/v1`:

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/api/v1/documents` | Carga de archivo PDF o DOCX. Retorna `job_id`. |
| `POST` | `/api/v1/documents/{job_id}/analyze` | Extrae bloques y ejecuta la detección de PII. |
| `GET` | `/api/v1/documents/{job_id}/analysis` | Consulta el listado de entidades detectadas y métricas. |
| `PATCH`| `/api/v1/documents/{job_id}/detections` | Modifica selecciones, descarta falsos positivos o añade entidades. |
| `POST` | `/api/v1/documents/{job_id}/anonymize` | Ejecuta la anonimización física según la estrategia elegida. |
| `GET` | `/api/v1/documents/{job_id}/download` | Descarga el archivo anonimizado final. |
| `DELETE`| `/api/v1/documents/{job_id}` | Elimina el trabajo y destruye los archivos temporales asociados. |
| `GET` | `/api/v1/health` | Estado de salud del servicio y cantidad de trabajos activos. |

---

## 🧪 Pruebas Automatizadas

La suite de pruebas incluye tests unitarios para validadores algorítmicos, pruebas de motores documentales con verificación residual y tests de integración end-to-end sobre la API REST:

```bash
PYTHONPATH=. pytest -v
```

Todas las pruebas deben ejecutarse y pasar con 0 errores:
```
tests/test_anondoc.py::test_ecuador_cedula_valid PASSED
tests/test_anondoc.py::test_ecuador_cedula_invalid_checksum PASSED
tests/test_anondoc.py::test_ecuador_cedula_invalid_province PASSED
tests/test_anondoc.py::test_ecuador_ruc_natural PASSED
tests/test_anondoc.py::test_luhn_credit_card PASSED
tests/test_anondoc.py::test_ipv4_validation PASSED
tests/test_anondoc.py::test_hybrid_pii_detection PASSED
tests/test_anondoc.py::test_anonymization_strategies PASSED
tests/test_anondoc.py::test_storage_security_path_traversal PASSED
tests/test_anondoc.py::test_storage_magic_bytes_check PASSED
tests/test_anondoc.py::test_pdf_native_redaction_and_verification PASSED
tests/test_anondoc.py::test_docx_anonymization_and_metadata_scrubbing PASSED
tests/test_anondoc.py::test_rest_api_e2e_flow PASSED
```

---

## ⚠️ Limitaciones Conocidas

1. **PDFs Escaneados:** Si un PDF consiste exclusivamente en imágenes escaneadas sin una capa de texto OCR preexistente, el sistema alertará que la página contiene una imagen sin texto seleccionable.
2. **Textos en Curvas Vectoriales:** Textos convertidos a curvas o trazados vectoriales gráficos (por ejemplo en logotipos de cabecera) no son reconocidos como caracteres de texto por los extractores de flujo.
3. **Imágenes con Texto Incrustado:** AnonDoc anonimiza flujos de texto, metadatos y tablas; no realiza OCR en imágenes fotográficas incrustadas en el cuerpo del documento por defecto para mantener un bajo consumo de memoria.
