"""Smoke test E2E do fluxo completo, incluindo dashboard, reports e fila de PDF."""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000"
TOKEN = None


def call(method, path, body=None, token=None, raw=False):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data) as resp:
            content = resp.read()
            return resp.status, content if raw else json.loads(content)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


import random
email = f"e2e_{random.randint(1000,9999)}@test.com"

print("register:", call("POST", "/auth/register", {"name": "E2E", "email": email, "password": "senha12345"}))
code, data = call("POST", "/auth/login", {"email": email, "password": "senha12345"})
TOKEN = data["access_token"]
print("login ok")

code, client = call("POST", "/clients", {"full_name": "Cliente E2E"}, TOKEN)
print("client:", code, client["id"])
cid = client["id"]

code, sale = call("POST", "/sales", {
    "client_id": cid, "sale_date": "2026-09-07", "status": "pending",
    "due_date": "2026-10-07",
    "items": [{"product_name": "Produto A", "quantity": 2, "unit_price": 15.50},
              {"product_name": "Produto B", "quantity": 1, "unit_price": 99.90}],
}, TOKEN)
print("sale:", code, "total:", sale["total"])
sid = sale["id"]

print("get sale:", call("GET", f"/sales/{sid}", None, TOKEN)[0])
print("get client:", call("GET", f"/clients/{cid}", None, TOKEN)[0])
print("update client:", call("PUT", f"/clients/{cid}", {"full_name": "Cliente E2E Atualizado"}, TOKEN)[0])
print("dashboard:", call("GET", "/dashboard", None, TOKEN)[1])
print("report sales:", call("GET", "/reports/sales?start=2026-01-01&end=2026-12-31", None, TOKEN)[0])
print("report clients:", call("GET", "/reports/clients", None, TOKEN)[0])
print("report products:", call("GET", "/reports/products", None, TOKEN)[0])

code, job = call("POST", f"/queue/pdf/{sid}", None, TOKEN)
print("enqueue pdf:", code, job)
time.sleep(2)
code, status = call("GET", f"/queue/pdf/{job['job_id']}", None, TOKEN)
print("job status:", code, status["status"])
code, pdf = call("GET", f"/queue/pdf/{job['job_id']}/download", None, TOKEN, raw=True)
print("pdf download:", code, "bytes:", len(pdf), "header:", pdf[:8])

print("pay sale:", call("PATCH", f"/sales/{sid}/pay", None, TOKEN)[0])
print("delete client (deve falhar, tem venda):", call("DELETE", f"/clients/{cid}", None, TOKEN)[0])

from cleanup_test_data import *
