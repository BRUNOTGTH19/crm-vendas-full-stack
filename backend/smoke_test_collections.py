"""Teste funcional: edição de WhatsApp do cliente + cobrança personalizada.

Cobre:
- correção do bug de import em client_service.update_client (PUT /clients);
- central de cobranças (GET /collections/reminders);
- mensagem personalizada + link wa.me (GET /collections/message/{sale_id}).
"""
import sys
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
results = []


def check(name, ok, extra=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'} | {name} {extra}")


stamp = datetime.now().strftime("%H%M%S")
email = f"col_{stamp}@crm.com"
client_name = f"Carlos Souza {stamp}"

# Register + login
r = client.post("/auth/register", json={"name": "Col Test", "email": email, "password": "123456"})
check("register", r.status_code == 201, f"status={r.status_code}")
r = client.post("/auth/login", json={"email": email, "password": "123456"})
check("login", r.status_code == 200, f"status={r.status_code}")
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

# --- BUG FIX: editar cliente (update_client usava ClientUpdate sem import) ---
r = client.post("/clients", json={"full_name": client_name, "whatsapp": None}, headers=h)
check("create client", r.status_code == 201, f"status={r.status_code}")
client_id = r.json()["id"]

r = client.put(
    f"/clients/{client_id}",
    json={"full_name": client_name, "whatsapp": "+55 (86) 98888-7777"},
    headers=h,
)
check("update client whatsapp (bug fix)", r.status_code == 200, f"status={r.status_code} body={r.json()}")
check(
    "whatsapp persisted",
    r.status_code == 200 and r.json().get("whatsapp") == "+55 (86) 98888-7777",
    f"whatsapp={r.json().get('whatsapp')}",
)

# --- Venda pendente VENCIDA ---
r = client.post(
    "/sales",
    json={
        "client_id": client_id,
        "sale_date": date.today().isoformat(),
        "status": "pending",
        "due_date": (date.today() - timedelta(days=3)).isoformat(),
        "items": [{"product_name": "Produto Y", "quantity": 2, "unit_price": "150.00"}],
    },
    headers=h,
)
check("create overdue sale", r.status_code == 201, f"status={r.status_code}")
sale_id = r.json()["id"]

# --- Central de cobranças ---
r = client.get("/collections/reminders", headers=h)
check("reminders 200", r.status_code == 200, f"status={r.status_code}")
reminders = r.json()
mine = next((x for x in reminders if x["sale_id"] == sale_id), None)
check("overdue sale in reminders", mine is not None, f"found={mine is not None}")
check("reminder situation vencida", bool(mine and mine["situation"] == "vencida"),
      f"situation={mine and mine['situation']}")
check("reminder amount 300", bool(mine and mine["amount"] == "300.00"),
      f"amount={mine and mine['amount']}")

# --- Mensagem personalizada + wa.me ---
r = client.get(f"/collections/message/{sale_id}", headers=h)
check("message 200", r.status_code == 200, f"status={r.status_code}")
msg = r.json()
check("message has client name", client_name in msg["message"], f"msg={msg['message'][:60]!r}")
check("message has amount", "300,00" in msg["message"], f"msg={msg['message']!r}")
check("message has vencida line", "VENCIDO" in msg["message"], f"msg={msg['message']!r}")
check("has_phone true", msg["has_phone"] is True, f"has_phone={msg['has_phone']}")
check("whatsapp_digits normalized", msg["whatsapp_digits"] == "5586988887777",
      f"digits={msg['whatsapp_digits']}")
check("wa_link built", bool(msg["wa_link"] and msg["wa_link"].startswith("https://wa.me/5586988887777?text=")),
      f"wa_link={msg['wa_link']}")

# --- Cliente sem WhatsApp: has_phone False e wa_link None ---
r = client.post("/clients", json={"full_name": f"Sem Zap {stamp}"}, headers=h)
noid = r.json()["id"]
r = client.post(
    "/sales",
    json={
        "client_id": noid,
        "sale_date": date.today().isoformat(),
        "status": "pending",
        "due_date": date.today().isoformat(),
        "items": [{"product_name": "Produto Z", "quantity": 1, "unit_price": "50.00"}],
    },
    headers=h,
)
noid_sale = r.json()["id"]
r = client.get(f"/collections/message/{noid_sale}", headers=h)
check("no phone -> has_phone false", r.json()["has_phone"] is False, f"body={r.json()}")
check("no phone -> wa_link null", r.json()["wa_link"] is None, f"wa_link={r.json()['wa_link']}")

# --- Sem token -> 401 ---
r = client.get("/collections/reminders")
check("reminders no token 401", r.status_code == 401, f"status={r.status_code}")

# --- cleanup ---
from database import SessionLocal
from models.payment import Payment
from models.sale import Sale
from models.sale_item import SaleItem
from models.user import User

db = SessionLocal()
user = db.query(User).filter(User.email == email).first()
if user:
    for c in user.clients:
        for s in c.sales:
            db.query(Payment).filter(Payment.sale_id == s.id).delete(synchronize_session=False)
            db.query(SaleItem).filter(SaleItem.sale_id == s.id).delete(synchronize_session=False)
            db.delete(s)
        db.commit()
    for c in list(user.clients):
        db.delete(c)
    db.commit()
    db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
    db.commit()
db.close()

fails = [n for n, ok in results if not ok]
print("=" * 40)
print(f"{len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)