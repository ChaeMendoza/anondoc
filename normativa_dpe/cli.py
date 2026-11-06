"""
Interfaz de línea de comandos (CLI) para la revisión normativa institucional de la Defensoría del Pueblo.
"""
import argparse
import sys
from pathlib import Path
from normativa_dpe.pipeline import NormativeReviewPipeline

def main():
    parser = argparse.ArgumentParser(
        description="Sistema de Revisión y Corrección del Informe de Análisis Normativo (Defensoría del Pueblo del Ecuador)"
    )
    parser.add_argument(
        "--proyecto",
        "-p",
        required=True,
        help="Ruta al archivo del Proyecto de Ley (.doc, .docx, .pdf)"
    )
    parser.add_argument(
        "--informe",
        "-i",
        required=True,
        help="Ruta al archivo del Informe de Análisis Normativo original de la DPE (.doc, .docx, .pdf)"
    )
    parser.add_argument(
        "--observaciones",
        "-o",
        required=True,
        help="Ruta al archivo o matriz de Observaciones institucionales (.doc, .docx, .pdf)"
    )
    parser.add_argument(
        "--output",
        "-d",
        default="output",
        help="Directorio de destino para los productos generados (default: output/)"
    )

    args = parser.parse_args()

    pipeline = NormativeReviewPipeline(output_dir=args.output)
    try:
        results = pipeline.run(
            proyecto_ley_path=args.proyecto,
            informe_dpe_path=args.informe,
            observaciones_path=args.observaciones
        )
        print("\n" + "="*70)
        print("RESUMEN DE PRODUCTOS GENERADOS:")
        print(f"1. Informe Word corregido:    {results['output_docx']}")
        print(f"2. Informe PDF corregido:     {results['output_pdf']}")
        print(f"3. Matriz Excel de cambios:   {results['output_excel']}")
        print(f"4. Reporte Calidad (Markdown):{results['output_qc_md']}")
        print(f"5. Reporte Calidad (JSON):    {results['output_qc_json']}")
        print("="*70)
    except Exception as e:
        print(f"\n[!] Error durante la ejecución del pipeline: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
