"""
Generador de documentos de prueba institucionales:
1. Proyecto de Ley de Fomento a la Alimentación Saludable y al Consumo de Proteína de Alto Valor Biológico.
2. Informe de Análisis Normativo original de la Defensoría del Pueblo del Ecuador (con la 5ta conclusión original).
3. Documento de Observaciones Institucionales.
"""
from pathlib import Path
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

def build_sample_files(output_dir: str = "sample_input"):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------
    # 1. PROYECTO DE LEY
    # -------------------------------------------------------------
    doc_ley = docx.Document()
    h1 = doc_ley.add_paragraph()
    h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = h1.add_run("ASAMBLEA NACIONAL DE LA REPÚBLICA DEL ECUADOR\n")
    r1.bold = True
    r1.font.size = Pt(14)
    r2 = h1.add_run("PROYECTO DE LEY ORGÁNICA DE FOMENTO A LA ALIMENTACIÓN SALUDABLE Y AL CONSUMO DE PROTEÍNA DE ALTO VALOR BIOLÓGICO\n")
    r2.bold = True
    r2.font.size = Pt(12)

    doc_ley.add_paragraph("CONSIDERANDO:\nQue el artículo 13 de la Constitución de la República consagra el derecho de las personas y colectividades al acceso seguro y permanente a alimentos sanos, suficientes y nutritivos...")

    doc_ley.add_heading("CAPÍTULO II - DE LOS DERECHOS NUTRICIONALES", level=2)
    
    p_art6 = doc_ley.add_paragraph()
    r_art6 = p_art6.add_run("Artículo 6.- Derecho a la orientación nutricional individualizada. ")
    r_art6.bold = True
    p_art6.add_run(
        "Toda persona tiene derecho a recibir información y asesoramiento técnico sobre nutrición adecuada, "
        "personalizada e integral según su etapa del ciclo de vida, condiciones metabólicas, requerimientos biológicos "
        "y contexto socioeconómico, garantizando la promoción de estilos de vida saludables y la prevención de enfermedades no transmisibles."
    )

    doc_ley.add_heading("CAPÍTULO III - DE LAS GUÍAS Y POLÍTICAS ALIMENTARIAS", level=2)

    p_art8 = doc_ley.add_paragraph()
    r_art8 = p_art8.add_run("Artículo 8.- De la actualización de la guía alimentaria nacional y rol prioritario. ")
    r_art8.bold = True
    p_art8.add_run(
        "La autoridad sanitaria nacional actualizará de manera periódica la guía alimentaria nacional, otorgando "
        "un rol prioritario a la proteína de alto valor biológico dentro de los esquemas nutricionales sugeridos, compras públicas, "
        "programas de alimentación escolar y estrategias estatales de combate a la malnutrición."
    )

    path_ley = out_path / "proyecto_de_ley.docx"
    doc_ley.save(path_ley)

    # -------------------------------------------------------------
    # 2. INFORME DE ANÁLISIS NORMATIVO ORIGINAL DE LA DPE
    # -------------------------------------------------------------
    doc_dpe = docx.Document()
    h_dpe = doc_dpe.add_paragraph()
    h_dpe.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_d1 = h_dpe.add_run("DEFENSORÍA DEL PUEBLO DEL ECUADOR\n")
    r_d1.bold = True
    r_d1.font.size = Pt(14)
    r_d1.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    
    r_d2 = h_dpe.add_run("DIRECCIÓN NACIONAL DE ANÁLISIS NORMATIVO Y TUTELA DE DERECHOS\n")
    r_d2.bold = True
    r_d2.font.size = Pt(11)

    r_d3 = h_dpe.add_run("INFORME DE ANÁLISIS NORMATIVO NRO. DPE-DNAN-2026-042\n")
    r_d3.font.size = Pt(10)
    r_d3.italic = True

    doc_dpe.add_heading("I. ANTECEDENTES Y COMPETENCIA INSTITUCIONAL", level=1)
    doc_dpe.add_paragraph(
        "La Defensoría del Pueblo del Ecuador, conforme a las atribuciones conferidas por el artículo 215 de la Constitución "
        "de la República y su Ley Orgánica, emite el presente criterio técnico-jurídico sobre la iniciativa legislativa remitida por la Asamblea Nacional."
    )

    doc_dpe.add_heading("II. ANÁLISIS CONSTITUCIONAL Y TÉCNICO DEL ARTICULADO", level=1)
    
    doc_dpe.add_heading("2.1. Análisis del Artículo 6 (Orientación Nutricional)", level=2)
    doc_dpe.add_paragraph(
        "El artículo 6 introduce un avance positivo en materia de autodeterminación informativa y acceso a la salud preventiva, "
        "al consagrar la orientación nutricional individualizada con enfoque de ciclo de vida."
    )

    doc_dpe.add_heading("2.2. Análisis del Artículo 8 (Guía Alimentaria y Proteína)", level=2)
    p_obs8 = doc_dpe.add_paragraph()
    p_obs8.add_run("Observación al Artículo 8: ").bold = True
    p_obs8.add_run(
        "Se constata que la propuesta legislativa pretende imponer desde el rango legal una prelación a la proteína de alto valor biológico. "
        "Al respecto, se advierte que la fijación de estándares dietéticos responde a criterios epidemiológicos dinámicos y evidencia científica mutable."
    )

    doc_dpe.add_heading("III. CONCLUSIONES", level=1)
    doc_dpe.add_paragraph("Primera.- El proyecto persigue fines legítimos orientados al fomento de la nutrición saludable.")
    doc_dpe.add_paragraph("Segunda.- Se reconoce la pertinencia de promover hábitos alimenticios balanceados en la población escolar.")
    doc_dpe.add_paragraph("Tercera.- Se valora positivamente la consagración del derecho a la orientación nutricional individualizada en el artículo 6.")
    doc_dpe.add_paragraph("Cuarta.- Es indispensable que las políticas alimentarias articulen la producción local y la soberanía alimentaria.")
    
    # Quinta conclusión original con la frase que requiere sustitución técnica:
    p_c5 = doc_dpe.add_paragraph()
    r_c5_num = p_c5.add_run("Quinta.- ")
    r_c5_num.bold = True
    p_c5.add_run(
        "Se considera que la jerarquización obligatoria establecida en el articulado podría obstaculizar el ejercicio efectivo del derecho a la salud "
        "de las personas y grupos de atención prioritaria, al desatender las particularidades alimentarias territoriales."
    )

    path_dpe = out_path / "informe_dpe_original.docx"
    doc_dpe.save(path_dpe)

    # -------------------------------------------------------------
    # 3. DOCUMENTO DE OBSERVACIONES INSTITUCIONALES
    # -------------------------------------------------------------
    doc_obs = docx.Document()
    h_obs = doc_obs.add_paragraph()
    h_obs.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_o1 = h_obs.add_run("MATRIZ DE OBSERVACIONES TÉCNICO-JURÍDICAS\n")
    r_o1.bold = True
    r_o1.font.size = Pt(13)

    table = doc_obs.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Artículo del Proyecto"
    hdr_cells[1].text = "Texto Observado"
    hdr_cells[2].text = "Criterio Jurídico Institucional"

    row_cells = table.add_row().cells
    row_cells[0].text = "Artículo 8"
    row_cells[1].text = "Actualización de la guía alimentaria otorgando rol prioritario a la proteína de alto valor biológico."
    row_cells[2].text = (
        "La ley no debe petrificar jerarquías nutricionales. Se debe preservar la potestad técnica de la autoridad sanitaria nacional "
        "para actualizar las directrices dietéticas conforme a la evidencia científica, etapas de vida, diversidad cultural y condiciones de acceso."
    )

    path_obs = out_path / "observaciones_institucionales.docx"
    doc_obs.save(path_obs)

    print(f"[✓] Documentos de prueba creados en '{output_dir}':")
    print(f"    - {path_ley}")
    print(f"    - {path_dpe}")
    print(f"    - {path_obs}")

if __name__ == "__main__":
    build_sample_files()
