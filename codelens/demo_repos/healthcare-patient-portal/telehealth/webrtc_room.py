"""
telehealth/webrtc_room.py - WebRTC session negotiation and ephemeral room token generator.
"""
import secrets


def create_webrtc_room(patient_id: str, physician_id: str) -> dict:
    """Create a WebRTC video consultation signaling room with an ephemeral token."""
    room_id = f"room_{patient_id}_{physician_id}"
    token = secrets.token_urlsafe(16)
    return {
        "room_id": room_id,
        "signaling_token": token,
        "ice_servers": [{"urls": "stun:stun.l.google.com:19302"}],
    }
