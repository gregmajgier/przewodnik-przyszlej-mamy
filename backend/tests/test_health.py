def test_health_ok(client):
    assert client.get("/health").json() == {"status": "ok"}
