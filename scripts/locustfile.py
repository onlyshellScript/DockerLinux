# Locust load test for SIGOS (RNF-01/RNF-02)
# Run: locust -f scripts/locustfile.py --host=http://localhost:5000
from locust import HttpUser, task, between

# SigosUser: clase auxiliar para SigosUser.
class SigosUser(HttpUser):
    wait_time = between(1, 3)

# Inicia la prueba autenticando al usuario admin y guardando el token JWT para las peticiones siguientes.
    def on_start(self):
        r = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
        self.token = r.json().get("access_token", "")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
# Lista órdenes de trabajo paginadas para simular carga de lectura en el listado principal.
    def list_orders(self):
        self.client.get("/api/v1/work-orders?page=1&page_size=20", headers=self.headers)

    @task(2)
# Filtra órdenes por estado y zona para simular consultas con parámetros de búsqueda.
    def filter_orders(self):
        self.client.get("/api/v1/work-orders?status=pending&zone=Z1", headers=self.headers)

    @task(1)
# Crea una nueva orden de trabajo para medir el rendimiento del endpoint de escritura.
    def create_order(self):
        self.client.post("/api/v1/work-orders", headers=self.headers, json={"title": "Load test order"})

    @task(1)
# Consulta el reporte de órdenes para validar el rendimiento de agregaciones y paginación.
    def report_orders(self):
        self.client.get("/api/v1/reportes/ordenes?por_pagina=20", headers=self.headers)
