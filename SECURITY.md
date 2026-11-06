# Seguridad de AnonDoc

Este documento resume la auditoría realizada, los controles implementados, lo pendiente y los riesgos residuales. **No** afirma que la aplicación sea "totalmente segura": es una reducción de superficie de ataque verificada con pruebas automatizadas, no una certificación.

## 1. Hallazgos de la auditoría y estado

| # | Severidad | Hallazgo | CWE / OWASP | Estado |
|---|-----------|----------|-------------|--------|
| 1 | Alta | Sin autorización: el `job_id` bastaba para leer, anonimizar, descargar o borrar un trabajo (IDOR/BOLA) | CWE-639 / API1:2023 | Corregido (token por trabajo, 404 uniforme) |
| 2 | Alta | Descarga permitida aunque la verificación residual fallara | CWE-693 | Corregido (fail-closed, salida eliminada) |
| 3 | Alta | Parseo de archivos hostiles en el proceso de la API, sin límites de recursos | CWE-400, CWE-770 | Mitigado (worker aislado con rlimits; sin aislamiento de red) |
| 4 | Alta | ZIP/DOCX: sin límites de entradas, ratio, duplicados, XXE, macros/OLE/relaciones externas | CWE-409, CWE-611 | Corregido |
| 5 | Alta | PDF: JavaScript/Launch/XFA/cifrado/adjuntos sin tratar | CWE-94 | Corregido (rechazo/sanitización) |
| 6 | Media | PII residual: anotaciones, adjuntos, metadatos, comentarios, notas, cuadros de texto, texto alternativo, miniaturas, autores; PDF buscaba solo en la página de la entidad; verificación ignoraba valores < 4 caracteres | CWE-212 | Corregido |
| 7 | Media | XSS por comillas sin escapar y `onclick` inline | CWE-79 / A03 | Corregido (escape, delegación de eventos, CSP) |
| 8 | Media | CORS `*` con credenciales | CWE-942 / A05 | Corregido (cerrado por defecto) |
| 9 | Media | Errores con `str(e)`, `temp_dir` en `/health`, nombre original en la descarga | CWE-209 / CWE-200 | Corregido |
| 10 | Media | Sin límites de tasa ni de tamaño de cuerpo | CWE-770 / API4:2023 | Corregido (por IP) |
| 11 | Media | ReDoS en la regex de correos (cuadrática, ~50 s con 200 KB) | CWE-1333 | Corregido (cuantificadores acotados) |
| 12 | Baja | Fuentes externas (Google Fonts); `HOST` 0.0.0.0 por defecto; Swagger expuesto | CWE-1104 / A05 | Corregido |
| 13 | Baja | Dependencias sin fijar y no usadas (`pandas`, `openpyxl`, LibreOffice en la imagen) | A06 | Corregido (pins exactos; eliminadas) |
| 14 | Baja | Mapa de seudónimos y entidades retenidos tras finalizar | CWE-212 | Corregido |

## 2. Controles implementados

- Token de capacidad por trabajo (`secrets`, comparación `hmac.compare_digest`, solo se guarda el hash). Solo por cabecera `Authorization`.
- Validación de formato por firma real y coherencia con la extensión; límites configurables (`ANONDOC_MAX_*`), ver `anondoc/config.py`.
- Worker en subproceso (`python -s -P -m anondoc.worker`) con entorno mínimo, `setsid`, `RLIMIT_AS/CPU/FSIZE/NOFILE/CORE`, timeout con kill del grupo de procesos y semáforo de concurrencia.
- Redacción/sanitización y verificación posterior; si falla, no se entrega.
- Directorio temporal 0700, archivos 0600, nombres internos (nunca el nombre del usuario), purga por TTL, al iniciar y al apagar.
- Cabeceras: CSP, `nosniff`, `X-Frame-Options: DENY`, `Cache-Control: no-store` en `/api`. Logs sin contenido ni PII; eventos de rechazo registrados sin datos del documento.
- Contenedor no root, `read_only`, `cap_drop: ALL`, `no-new-privileges`, límites de memoria/CPU/PIDs, tmpfs, puerto solo en loopback.
- CI (`.github/workflows/ci.yml`): pruebas, `ruff`, `bandit`, `pip-audit`, `gitleaks`, `hadolint`, `trivy`. Dependabot para pip, Docker y Actions.

## 3. Pendiente / mejoras recomendadas

- Aislamiento de red del worker (namespaces/`unshare`, `bubblewrap`, gVisor) y filtro seccomp; no está implementado.
- Límite de procesos por usuario (`RLIMIT_NPROC`) en el worker; en contenedor se limita con `pids_limit` (podman-compose 1.0.6 no lo aplicó al verificar).
- Autenticación de usuarios real y TLS (responsabilidad del reverse proxy); sin ellas, no exponga el servicio a Internet.
- Almacén de trabajos compartido para escalar a varios procesos; hoy es un solo proceso en memoria.
- Políticas SELinux/AppArmor específicas.

## 4. Riesgos residuales

- La detección de PII es heurística (regex + validadores): puede haber falsos negativos. La revisión humana es obligatoria.
- No se analiza texto en imágenes (sin OCR), ni texto vectorizado; se avisa como limitación cuando se detectan imágenes.
- `style-src 'unsafe-inline'` en la CSP por estilos inline estáticos de la interfaz.
- La limitación de tasa usa la IP del cliente; detrás de un proxy verá la IP del proxy.
- Los parsers (PyMuPDF, lxml) son código nativo: una vulnerabilidad 0-day podría comprometer el worker; por eso se aísla y se limita, pero sin aislamiento de red.
- Un token de acceso filtrado da acceso al trabajo hasta su expiración (30 min por defecto).

## 5. Pruebas no ejecutadas

- `gitleaks`, `trivy` y `hadolint` no estaban instalados en el entorno local: solo se ejecutan en CI.
- No se ejecutó prueba de carga ni pruebas con documentos reales; los documentos de prueba son sintéticos.

## 6. Actualización de dependencias

1. Dependabot abre PRs semanales. 2. `pip install -r requirements-dev.txt && pytest && pip-audit -r requirements.txt`. 3. Fije versiones exactas en `requirements.txt` (incluidas transitivas). 4. Reconstruya la imagen.

## 7. Respuesta a incidentes

1. Detenga el contenedor (`podman-compose down`): los temporales viven en tmpfs y se pierden. 2. Rote cualquier secreto del entorno. 3. Revise los logs del logger `anondoc.security` (rechazos). 4. Reporte la vulnerabilidad de forma privada al mantenedor antes de divulgarla. 5. Parchee, añada una prueba de regresión y reconstruya.

## 8. Configuración segura

- Producción: `ANONDOC_DEBUG=false`, `ANONDOC_ENABLE_DOCS` desactivado, `ANONDOC_CORS_ORIGINS` vacío salvo necesidad, TLS y autenticación en el proxy.
- Local con Podman/Docker: mantener el mapeo `127.0.0.1:8000:8000`.
