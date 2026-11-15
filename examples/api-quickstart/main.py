import json
import os
import urllib.request

BASE = "http://localhost:5000/api/v1"

def post(path, data, token=None):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))

def get(path, token=None):
    req = urllib.request.Request(BASE + path)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))

if __name__ == "__main__":
    print("Health:", get("/health"))
import os
...
    login = post("/auth/login", {"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "CAMBIAR_ESTE_VALOR")})
    token = login["access_token"]
    order = post("/work-orders", {"title": "Orden de ejemplo", "priority": "medium"}, token)
    print("Orden creada:", order["id"], order["status"])
