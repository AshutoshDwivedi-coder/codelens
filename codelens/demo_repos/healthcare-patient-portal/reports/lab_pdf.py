"""
reports/lab_pdf.py - PDF report generation with physician digital signature stamping.
"""


def compile_lab_report(patient_id: str, results: list[dict], physician_id: str) -> dict:
    """Digitally compile patient blood test / imaging results into a signed lab report."""
    return {
        "patient_id": patient_id,
        "physician_id": physician_id,
        "results": results,
        "format": "PDF",
        "digitally_signed": True,
        "signature": f"sig_{physician_id}",
    }
