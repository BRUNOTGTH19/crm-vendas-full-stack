"""Smoke test temporario - modulo de vendas (Fase 2)."""
import sys
from datetime import datetime

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models.client import Client
from models.sale import Sale
from models.sale_item import SaleItem
from models.user import User

client = TestClient(app)
results = []


def check(name: str, ok: bool, extra: str = '') -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'} | {name} {extra}")


email = f"sales_smoke_{datetime.now().strftime('%H%M%S')}@crm.com"

# register/login
r = client.post('/auth/register', json={'name':'Sales Smoke','email':email,'password':'123456'})
check('register', r.status_code == 201, f"status={r.status_code}")
r = client.post('/auth/login', json={'email':email,'password':'123456'})
token = r.json()['access_token']
headers = {'Authorization':'Bearer ' + token}

# create client
r = client.post('/clients', json={'full_name':'Sales Cliente'}, headers=headers)
check('create client', r.status_code == 201, f"status={r.status_code}")
client_id = r.json()['id']

# create sale pending com due_date (total esperado: 10.5*2 + 25 =  .46.0)
items1 = [{'product_name':'Produto A','quantity':2,'unit_price':10.5}, {'product_name':'Produto B','quantity':1,'unit_price':25}]
r = client.post('/sales', json={'client_id':client_id,'sale_date':'2026-09-07','status':'pending','due_date':'2026-09-30','items':items1}, headers=headers)
try:
    total_ok = float(r.json()['total']) == 46.0
except Exception:
    total_ok = False
ok = r.status_code == 201 and len(r.json()['items']) == 2 and total_ok
check('create sale total 46.00', ok, f"status={r.status_code} body={r.json()}")
sale_id = r.json()['id']

# default status pending (sem campo status
items2 = [{'product_name':'P','quantity':1,'unit_price':5}]
r = client.post('/sales', json={'client_id':client_id,'sale_date':'2026-09-08','due_date':'2026-10-05','items':items2}, headers=headers)
check('default status pending', r.status_code == 201 and r.json()['status'] == 'pending', f"status={r.status_code} body={r.json()}")

# pending sem due_date ->422
r = client.post('/sales', json={'client_id':client_id,'sale_date':'2026-09-08','items':items2}, headers=headers)
check('pending sem due_date 422', r.status_code == 422, f"status={r.status_code}")

# list
r = client.get('/sales', headers=headers)
check('list sales', r.status_code == 200 and len(r.json()) >= 2, f"status={r.status_code} count={len(r.json())}")

# filter pending
r = client.get('/sales?status=pending', headers=headers)
check('filter pending', r.status_code == 200 and len(r.json()) == 2, f"status={r.status_code} count={len(r.json())}")

# history by client
r = client.get(f"/sales/client/{client_id}", headers=headers)
check('history by client', r.status_code == 200 and len(r.json()) == 2, f"status={r.status_code} count={len(r.json())}")

# pay first sale (clears due_date
r = client.patch(f"/sales/{sale_id}/pay", headers=headers)
ok = r.status_code == 200 and r.json()['status'] == 'paid' and r.json()['due_date'] is None
check('pay sale clears due_date', ok, f"status={r.status_code} body={r.json()}")

# cliente inexistente ->400
r = client.post('/sales', json={'client_id':999999,'sale_date':'2026-09-08','due_date':'2026-10-05','items':items2}, headers=headers)
check('cliente inexistente 400', r.status_code == 400, f"status={r.status_code} detail={r.json()}")

# pay inexistente ->404
r = client.patch('/sales/99999/pay', headers=headers)
check('pay inexistente 404', r.status_code == 404, f"status={r.status_code}")

# no token
r = client.get('/sales')
check('no token 401', r.status_code == 401, f"status={r.status_code}")

# cleanup
print('--- cleanup ---')
db = SessionLocal()
u = db.query(User).filter(User.email == email).first()
if u:
    ids = [u.id]
    sale_ids = [s.id for s in db.query(Sale).filter(Sale.user_id.in_(ids)).all()]
    if sale_ids:
        db.query(SaleItem).filter(SaleItem.sale_id.in_(sale_ids)).delete(synchronize_session=False)
        db.query(Sale).filter(Sale.id.in_(sale_ids)).delete(synchronize_session=False)
    cl_ids = [c.id for c in db.query(Client).filter(Client.created_by_id.in_(ids)).all()]
    if cl_ids:
        s2 = [s.id for s in db.query(Sale).filter(Sale.client_id.in_(cl_ids)).all()]
        if s2:
            db.query(SaleItem).filter(SaleItem.sale_id.in_(s2)).delete(synchronize_session=False)
            db.query(Sale).filter(Sale.id.in_(s2)).delete(synchronize_session=False)
        db.query(Client).filter(Client.id.in_(cl_ids)).delete(synchronize_session=False)
    db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
print('users:', db.query(User).count(), '| clients:', db.query(Client).count(), '| sales:', db.query(Sale).count(), '| items:', db.query(SaleItem).count())
db.close()

fails = [n for n, ok in results if not ok]
print('=' * 40)
print(f"{len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)