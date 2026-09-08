"""Smoke test E2E das novas features da Fase A: logout/refresh/sessões e relatórios PDF."""
import json
import random
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
results = []


def check(name, ok, extra=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} | {name} {extra}")


def call(method, path, body=None, token=None, raw=False):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=15) as resp:
            content = resp.read()
            return resp.status, (content if raw else (json.loads(content) if content else None))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


email = f"faseA_{random.randint(1000, 9999)}@test.com"
rand = email.split("_")[1].split("@")[0]

# login
code, data = call("POST", "/auth/login", {"email": "bruno@crm.com", "password": "errada"})
check("login senha errada 401", code == 401)

# usa usuário de teste próprio
call("POST", "/auth/register", {"name": "FaseA", "email": email, "password": "senha12345"})
code, data = call("POST", "/auth/login", {"email": email, "password": "senha12345"})
check("login", code == 200)
token = data["access_token"]
refresh = data["refresh_token"]

# refresh de token
code, new_tokens = call("POST", "/auth/refresh", {"refresh_token": refresh})
check("refresh 200", code == 200 and "access_token" in new_tokens, f"status={code}")
check("novo access diferente", new_tokens["access_token"] != token)

# antigo access foi substituído na sessão → deve dar 401
code, _ = call("GET", "/auth/me", None, token)
check("access antigo revogado 401", code == 401)

# novo access funciona
code, _ = call("GET", "/auth/me", None, new_tokens["access_token"])
check("novo access funciona", code == 200)

# logout revoga a sessão
code, _ = call("POST", "/auth/logout", None, new_tokens["access_token"])
check("logout 204", code == 204)
code, _ = call("GET", "/auth/me", None, new_tokens["access_token"])
check("pos-logout 401", code == 401)
code, _ = call("POST", "/auth/refresh", {"refresh_token": new_tokens["refresh_token"]})
check("refresh pos-logout 401", code == 401)

# re-login para testar PDFs
code, data = call("POST", "/auth/login", {"email": email, "password": "senha12345"})
token = data["access_token"]

# dados de teste: cliente + venda paga e pendente
code, client = call("POST", "/clients", {"full_name": f"Cliente FaseA {rand}"}, token)
cid = client["id"]
code, sale1 = call("POST", "/sales", {
    "client_id": cid, "sale_date": "2026-09-08", "status": "paid",
    "items": [{"product_name": "Produto X", "quantity": 2, "unit_price": 30}],
}, token)
check("venda paga criada", code == 201)
code, sale2 = call("POST", "/sales", {
    "client_id": cid, "sale_date": "2026-09-08", "status": "pending",
    "due_date": "2026-09-08",
    "items": [{"product_name": "Produto Y", "quantity": 1, "unit_price": 45}],
}, token)
check("venda pendente criada", code == 201)

# relatórios PDF
code, pdf = call("GET", "/reports/paid?start=2026-01-01&end=2026-12-31", None, token, raw=True)
check("PDF vendas pagas", code == 200 and pdf[:5] == b"%PDF-", f"status={code} bytes={len(pdf)}")
code, pdf = call("GET", "/reports/pending", None, token, raw=True)
check("PDF pendentes", code == 200 and pdf[:5] == b"%PDF-")
code, pdf = call("GET", "/reports/charges", None, token, raw=True)
check("PDF cobrancas", code == 200 and pdf[:5] == b"%PDF-")
code, pdf = call("GET", "/reports/cashflow", None, token, raw=True)
check("PDF cashflow mes atual", code == 200 and pdf[:5] == b"%PDF-")
code, pdf = call("GET", "/reports/cashflow?month=2026-09", None, token, raw=True)
check("PDF cashflow mes especifico", code == 200 and pdf[:5] == b"%PDF-")
code, body = call("GET", "/reports/cashflow?month=xx", None, token)
check("cashflow mes invalido 400", code == 400)

# dashboard em cache (2a chamada deve ser identica)
code, d1 = call("GET", "/dashboard", None, token)
code, d2 = call("GET", "/dashboard", None, token)
check("dashboard cacheado", d1 == d2)

# limpar dados de teste
from cleanup_test_data import *  # noqa: E402,F403

fails = results.count(False)
print("=" * 40)
print(f"{len(results) - fails}/{len(results)} passed")
sys.exit(1 if fails else 0)
