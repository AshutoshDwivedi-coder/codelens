# CarePulse Healthcare & Patient Portal

HIPAA-compliant telemedicine and electronic health records (EHR) gateway with FHIR standard interoperability, appointment scheduling, and encrypted medical records.

## Key Features

- **FHIR HL7 Interoperability**: Ingests, parses, and validates clinical health resources formatted in the Fast Healthcare Interoperability Resources (FHIR R4) JSON standard.
- **HIPAA Field-Level Encryption**: Encrypts sensitive protected health information (PHI) using AES-256-GCM before persisting to database storage.
- **Smart Appointment Scheduler**: Resolves physician calendar booking slots, prevents double bookings, and sends automated SMS reminders.
- **Telehealth Video Signaling**: WebRTC signaling server enabling peer-to-peer end-to-end encrypted doctor-patient video consultations.
- **Diagnostic Lab Report Generator**: Digitally compiles and signs patient blood test results and diagnostic imaging reports into secure PDFs.

## System Architecture & Modules

- `records/fhir_parser.py`: FHIR R4 resource parsing, schema validation, and patient demographic mapping.
- `security/hipaa_encrypt.py`: AES-256-GCM PHI field encryption with AWS KMS envelope encryption.
- `appointments/scheduler.py`: Physician calendar availability algorithm and conflict resolution.
- `telehealth/webrtc_room.py`: WebRTC session negotiation and ephemeral room token generator.
- `reports/lab_pdf.py`: PDF report generation with physician digital signature stamping.

## Questions to Ask this Codebase

- How does the FHIR parser validate patient clinical records in `records/fhir_parser.py`?
- Where is AES-256 PHI encryption implemented in `security/hipaa_encrypt.py`?
- How does the appointment scheduler handle double booking conflicts in `appointments/scheduler.py`?
- Where is the WebRTC video consultation signaling room created in `telehealth/webrtc_room.py`?
- How are lab diagnostic reports compiled and digitally signed in `reports/lab_pdf.py`?
- Where are patient audit logging records stored for HIPAA compliance?
