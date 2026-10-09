from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
QUERY = {"lat": 0.5, "long": 0.5, "cat": "cafe", "rad": 0.1}


def test_search_returns_ten_ids():
    r = client.get("/search/", params=QUERY)
    assert r.status_code == 200
    body = r.json()
    assert list(body) == ["ids"]
    assert len(body["ids"]) == 10
    assert all(isinstance(i, int) for i in body["ids"])


def test_search_without_slash():
    r = client.get("/search", params=QUERY, follow_redirects=False)
    assert r.status_code == 200
    assert r.json() == client.get("/search/", params=QUERY).json()


def test_category_case_and_spaces():
    a = client.get("/search/", params=QUERY).json()
    b = client.get("/search/", params={**QUERY, "cat": "  CaFe "}).json()
    assert a == b


def test_debug_output():
    body = client.get("/search/", params={**QUERY, "debug": 1}).json()
    results = body["results"]
    assert [r["id"] for r in results] == body["ids"]
    hops = [r["road_segments"] for r in results]
    assert hops == sorted(hops)
    for r in results:
        assert r["route"][0] == body["pickup_node"]["id"]
        assert r["route"][-1] == r["id"]
        assert len(r["route"]) == r["road_segments"] + 1
        assert r["straight_line"] <= QUERY["rad"] + 1e-6


def test_bad_input_gives_400():
    bad_queries = [
        {"long": 0.5, "cat": "cafe", "rad": 0.1},
        {**QUERY, "lat": "abc"},
        {**QUERY, "cat": "spaceport"},
        {**QUERY, "rad": -1},
        {**QUERY, "rad": "nan"},
        {"lat": 0.5, "long": 0.5, "rad": 0.1},
    ]
    for q in bad_queries:
        r = client.get("/search/", params=q)
        assert r.status_code == 400, q
        assert "error" in r.json()


def test_health_and_demo_page():
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["locations"] == 10000
    assert health["roads"] == 14800
    assert client.get("/").status_code == 200
    assert len(client.get("/network").json()["missing"]) == 5000
