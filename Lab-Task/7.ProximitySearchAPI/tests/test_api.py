from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
Q = {"lat": 0.5, "long": 0.5, "cat": "cafe", "rad": 0.1}


def test_search_route_and_shape():
    r = client.get("/search/", params=Q)
    assert r.status_code == 200
    body = r.json()
    assert list(body) == ["ids"]
    assert len(body["ids"]) == 10 and all(isinstance(i, int) for i in body["ids"])


def test_no_slash_variant_answers_directly():
    r = client.get("/search", params=Q, follow_redirects=False)
    assert r.status_code == 200
    assert r.json() == client.get("/search/", params=Q).json()


def test_category_is_case_and_space_insensitive():
    a = client.get("/search/", params=Q).json()
    b = client.get("/search/", params={**Q, "cat": "  CaFe "}).json()
    assert a == b


def test_debug_explains_results():
    body = client.get("/search/", params={**Q, "debug": 1}).json()
    res = body["results"]
    assert [x["id"] for x in res] == body["ids"]
    assert [x["road_segments"] for x in res] == sorted(x["road_segments"] for x in res)
    for x in res:
        assert x["route"][0] == body["pickup_node"]["id"] and x["route"][-1] == x["id"]
        assert len(x["route"]) == x["road_segments"] + 1
        assert x["straight_line"] <= Q["rad"] + 1e-6


def test_validation_errors_are_400():
    for bad in ({"long": 0.5, "cat": "cafe", "rad": 0.1},
                {**Q, "lat": "abc"},
                {**Q, "cat": "spaceport"},
                {**Q, "rad": -1},
                {**Q, "rad": "nan"},
                {k: v for k, v in Q.items() if k != "cat"}):
        r = client.get("/search/", params=bad)
        assert r.status_code == 400, bad
        assert "error" in r.json()


def test_health_and_demo():
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["locations"] == 10_000 and h["roads"] == 14_800
    assert client.get("/").status_code == 200
    net = client.get("/network").json()
    assert len(net["missing"]) == 19_800 - 14_800
