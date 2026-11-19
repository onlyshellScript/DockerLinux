# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.
from app.health.service import check_health

# test_health_service_up: valida el escenario health service up preparando datos, ejecutando la accion y comprobando el resultado esperado.

# Session: clase auxiliar para Session.
def test_health_service_up():
    class Session:
        def execute(self, statement):
            return None

        def rollback(self):
            pass

    body, status = check_health(Session())
    assert status == 200
    assert body["status"] == "UP"

# test_health_endpoint: valida el escenario health endpoint preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "UP"
