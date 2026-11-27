def test_rate_limit(eng):
    client = TestClient(create_app(engine=eng, api_key="", rate_limit=2))
    body = {"text": "Merhaba dünya", "source": "tr", "target": "en"}
    assert client.post("/v1/translate", json=body).status_code == 200
    assert client.post("/v1/translate", json=body).status_code == 200
    res = client.post("/v1/translate", json=body)
    assert res.status_code == 429 and int(res.headers["Retry-After"]) > 0
    assert client.get("/v1/health").status_code == 200   # health is never limited


def test_rate_limit_with_api_key_is_shared_across_client_ips(eng):
    app = create_app(engine=eng, api_key="shared-secret", rate_limit=1)
    client_a = TestClient(app, client=("192.0.2.1", 1234))
    client_b = TestClient(app, client=("192.0.2.2", 1234))
    body = {"text": "Merhaba dünya", "source": "tr", "target": "en"}
    headers = {"Authorization": "Bearer shared-secret"}

    assert client_a.post("/v1/translate", json=body, headers=headers).status_code == 200
    # The configured key is the rate-limit identity, so changing IP cannot reset its quota.
    assert client_b.post("/v1/translate", json=body, headers=headers).status_code == 429
