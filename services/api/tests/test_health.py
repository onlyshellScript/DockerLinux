from app.health.service import check_health


def test_health_service_up():
    class Session:
        def execute(self, statement):
            return None

        def rollback(self):
            pass

    body, status = check_health(Session())
    assert status == 200
    assert body["status"] == "UP"


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "UP"
