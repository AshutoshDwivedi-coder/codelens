"""
fhir_parser.py - FHIR R4 Patient resource validation and parsing.
"""
import json

def parse_patient_resource(raw_json: str) -> dict:
    """Parse and validate FHIR Patient JSON object."""
    data = json.loads(raw_json)
    if data.get("resourceType") != "Patient":
        raise ValueError("Invalid FHIR resource: Expected Patient")
    
    patient_id = data.get("id", "unknown")
    name_entries = data.get("name", [{}])
    given = name_entries[0].get("given", [""])[0]
    family = name_entries[0].get("family", "")
    
    return {
        "id": patient_id,
        "full_name": f"{given} {family}".strip(),
        "birth_date": data.get("birthDate"),
        "gender": data.get("gender"),
    }
