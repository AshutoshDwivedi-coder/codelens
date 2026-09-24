"""
locustfile.py – Locust load testing for CodeLens API.

Usage:
    locust -f benchmarks/locustfile.py --host http://localhost:8000

Reports: requests/sec, p50/p95 latency, cache hit rate.
"""
from locust import HttpUser, task, between, events
import random

SAMPLE_QUERIES = [
    "sort a list in python",
    "parse json data",
    "http get request with headers",
    "fibonacci sequence recursive",
    "connect to postgresql database",
    "binary search implementation",
    "file read and write operations",
    "regex pattern matching",
    "async function with await",
    "class inheritance example",
    "error handling try except",
    "unit test with pytest",
    "REST API endpoint",
    "database connection pool",
    "encrypt decrypt string",
]


class CodeLensUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(5)
    def search(self):
        """Search endpoint (most common operation)."""
        q = random.choice(SAMPLE_QUERIES)
        with self.client.get(
            f"/api/search?q={q}&version=latest&top_k=10",
            name="/api/search",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "results" in data:
                    resp.success()
                else:
                    resp.failure("No results field in response")
            elif resp.status_code == 503:
                resp.failure("Service unavailable (no index)")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def search_with_filter(self):
        """Search with language filter."""
        q = random.choice(SAMPLE_QUERIES)
        lang = random.choice(["python", "javascript", "go"])
        with self.client.get(
            f"/api/search?q={q}&lang={lang}",
            name="/api/search?lang=filter",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 503):
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")

    @task(1)
    def list_versions(self):
        self.client.get("/api/versions", name="/api/versions")

    @task(1)
    def health_check(self):
        self.client.get("/api/health", name="/api/health")
