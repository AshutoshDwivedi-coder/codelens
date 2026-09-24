"""
test_readme_analyzer.py – Unit tests for README analyzer service and API endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.readme_analyzer import analyze_readme, resolve_repo_dir, find_readme_file


@pytest.fixture
def client():
    return TestClient(app)


def test_analyze_readme_root():
    result = analyze_readme(None)
    assert result["has_readme"] is True
    assert "CodeLens" in result["title"]
    assert len(result["suggested_questions"]) > 0
    assert any("pipeline" in q.lower() or "bm25" in q.lower() for q in result["suggested_questions"])


def test_analyze_readme_ecommerce():
    result = analyze_readme("ecommerce-platform")
    assert result["has_readme"] is True
    assert "ShopFlow" in result["title"] or "E-Commerce" in result["title"]
    # Verify questions are personal to this chosen repo
    assert any("stripe" in q.lower() or "cart" in q.lower() or "checkout" in q.lower() for q in result["suggested_questions"])
    assert not any("tree-sitter" in q.lower() for q in result["suggested_questions"])


def test_analyze_readme_auth_vault():
    result = analyze_readme("auth-security-vault")
    assert result["has_readme"] is True
    assert "Vault" in result["title"] or "Security" in result["title"]
    # Verify questions are personal to auth repo
    assert any("jwt" in q.lower() or "oauth2" in q.lower() or "argon2" in q.lower() for q in result["suggested_questions"])


def test_analyze_readme_healthcare():
    result = analyze_readme("healthcare-patient-portal")
    assert result["has_readme"] is True
    assert "CarePulse" in result["title"] or "Healthcare" in result["title"]
    # Verify questions are personal to healthcare repo
    assert any("fhir" in q.lower() or "hipaa" in q.lower() or "appointment" in q.lower() for q in result["suggested_questions"])


def test_analyze_readme_nonexistent(tmp_path):
    result = analyze_readme(str(tmp_path))
    assert "suggested_questions" in result
    assert len(result["suggested_questions"]) > 0


def test_api_readme_analyze_get(client):
    res = client.get("/api/readme/analyze?repo_path=ecommerce-platform")
    assert res.status_code == 200
    data = res.json()
    assert data["has_readme"] is True
    assert any("stripe" in q.lower() or "cart" in q.lower() for q in data["suggested_questions"])


def test_api_readme_analyze_post(client):
    res = client.post("/api/readme/analyze", json={"repo_path": "auth-security-vault"})
    assert res.status_code == 200
    data = res.json()
    assert data["has_readme"] is True
    assert "Vault" in data["title"] or "Security" in data["title"]
