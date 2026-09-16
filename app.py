from datetime import datetime, timedelta
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import time
from flask import Flask, jsonify, redirect, render_template, request, send_file

try:
  import qrcode
except ImportError:
  qrcode = None

BASE = Path(__file__).resolve().parent
DB = BASE / "foodstall.db"
app = Flask(__name__)

DEFAULT_ITEMS = [
    {"name": "Vanilla Cupcake", "price": 60.0},
    {"name": "Red Velvet Cupcake", "price": 60.0},
    {"name": "Lemon Cupcake", "price": 60.0},
    {"name": "Chocolate Cupcake", "price": 65.0},
    {"name": "Chocolate Overload Cookie", "price": 60.0},
    {"name": "Choc Chip Cookie", "price": 50.0},
    {"name": "Veg Sandwich", "price": 60.0},
    {"name": "Cheese Sandwich", "price": 70.0},
    {"name": "Chips Chaat", "price": 50.0},
    {"name": "Pav Bhaji", "price": 80.0},
    {"name": "Classic Sweet Lemonade", "price": 40.0},
    {"name": "Sweet & Sour Lemonade", "price": 40.0},
    {"name": "Strawberry Crush Lemonade", "price": 45.0},
    {"name": "Egg Brownie", "price": 60.0},
    {"name": "Eggless Brownie", "price": 60.0},
]


def db():
  con = sqlite3.connect(DB)
  con.row_factory = sqlite3.Row
  return con


def init_db():
  con = db()
  con.executescript("""
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY, value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        customer TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        items_json TEXT NOT NULL,
        subtotal REAL NOT NULL,
        discount REAL NOT NULL DEFAULT 0,
        total REAL NOT NULL,
        payment TEXT NOT NULL DEFAULT 'Pending',
        status TEXT NOT NULL DEFAULT 'Received',
        created_at TEXT NOT NULL,
        ready_at TEXT
    );
    """)
  if con.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
    con.executemany(
        "INSERT INTO settings(key,value) VALUES(?,?)",
        [
            ("discount_percent", "0"),
            ("minutes_per_order", "4"),
            ("upi_id", ""),
            ("stall_name", "NextGen Food Stall"),
        ],
    )
  if con.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0:
    con.executemany(
        "INSERT INTO items(name,price,stock) VALUES(?,?,?)",
        [(x["name"], x["price"], 25) for x in DEFAULT_ITEMS],
    )
  con.commit()
  con.close()


# Initialize database automatically on startup (crucial for Render/Gunicorn)
init_db()


def setting(key):
  con = db()
  r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
  con.close()
  return r["value"] if r else ""


def set_setting(key, value):
  con = db()
  con.execute(
      "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value))
  )
  con.commit()
  con.close()


def next_token():
  con = db()
  today = datetime.now().strftime("%Y%m%d")
  rows = con.execute(
      "SELECT token FROM orders WHERE token LIKE ?", (today + "-%",)
  ).fetchall()
  n = max([int(r["token"].split("-")[-1]) for r in rows] or [0]) + 1
  con.close()
  return f"{today}-{n:03d}"


def active_items():
  con = db()
  rows = con.execute(
      "SELECT * FROM items WHERE active=1 ORDER BY id"
  ).fetchall()
  con.close()
  return [dict(r) for r in rows]


def order_dict(r):
  d = dict(r)
  d["items"] = json.loads(d.pop("items_json"))
  return d


@app.route("/")
def customer():
  return render_template("customer.html", stall=setting("stall_name"))


@app.route("/order/<token>")
def track(token):
  return render_template("order.html", token=token)


@app.route("/admin")
def admin():
  return render_template("admin.html", stall=setting("stall_name"))


@app.route("/packing")
def packing():
  return render_template("packing.html", stall=setting("stall_name"))


@app.route("/display")
def display():
  return render_template("display.html", stall=setting("stall_name"))


@app.route("/qr")
def qr():
  if not qrcode:
    return "Install qrcode first: pip install qrcode[pil]", 500
  host = request.host_url.rstrip("/")
  img = qrcode.make(host + "/")
  buf = io.BytesIO()
  img.save(buf, format="PNG")
  buf.seek(0)
  return send_file(buf, mimetype="image/png")


@app.get("/api/items")
def api_items():
  return jsonify({
      "items": active_items(),
      "discount": float(setting("discount_percent") or 0),
      "upi_id": setting("upi_id"),
  })


@app.post("/api/order")
def create_order():
  data = request.get_json(force=True)
  cart = data.get("items", [])
  if not cart:
    return jsonify(error="Please select at least one item."), 400
  con = db()
  ids = [int(x["id"]) for x in cart]
  placeholders = ",".join("?" * len(ids))
  rows = con.execute(
      f"SELECT * FROM items WHERE id IN ({placeholders}) AND active=1", ids
  ).fetchall()
  lookup = {r["id"]: dict(r) for r in rows}
  subtotal = 0
  clean = []
  for x in cart:
    iid = int(x["id"])
    qty = int(x["qty"])
    if iid not in lookup or qty < 1:
      continue
    item = lookup[iid]
    if qty > item["stock"]:
      con.close()
      return (
          jsonify(error=f"Only {item['stock']} of {item['name']} available."),
          400,
      )
    subtotal += item["price"] * qty
    clean.append(
        {"id": iid, "name": item["name"], "qty": qty, "price": item["price"]}
    )
  if not clean:
    con.close()
    return jsonify(error="Invalid order."), 400
  discount_pct = float(setting("discount_percent") or 0)
  discount = round(subtotal * discount_pct / 100, 2)
  total = round(subtotal - discount, 2)
  token = next_token()
  created = datetime.now().isoformat(timespec="seconds")
  con.execute(
      """INSERT INTO orders(token,customer,phone,items_json,subtotal,discount,total,created_at)
                VALUES(?,?,?,?,?,?,?,?)""",
      (
          token,
          data.get("customer", ""),
          data.get("phone", ""),
          json.dumps(clean),
          subtotal,
          discount,
          total,
          created,
      ),
  )
  for x in clean:
    con.execute(
        "UPDATE items SET stock=stock-? WHERE id=?", (x["qty"], x["id"])
    )
  con.commit()
  con.close()
  return jsonify(
      token=token, total=total, discount=discount, eta=estimate_eta(token)
  )


def estimate_eta(token):
  con = db()
  r = con.execute("SELECT id FROM orders WHERE token=?", (token,)).fetchone()
  if not r:
    con.close()
    return 0
  pending = con.execute(
      "SELECT COUNT(*) c FROM orders WHERE status IN ('Received','Packing')"
      " AND id<=?",
      (r["id"],),
  ).fetchone()["c"]
  con.close()
  return max(2, pending * int(setting("minutes_per_order") or 4))


@app.get("/api/orders")
def orders():
  con = db()
  rows = con.execute(
      "SELECT * FROM orders ORDER BY id DESC LIMIT 100"
  ).fetchall()
  con.close()
  return jsonify({"orders": [order_dict(r) for r in rows]})


@app.get("/api/order/<token>")
def order_status(token):
  con = db()
  r = con.execute("SELECT * FROM orders WHERE token=?", (token,)).fetchone()
  con.close()
  if not r:
    return jsonify(error="Token not found"), 404
  d = order_dict(r)
  d["eta"] = estimate_eta(token)
  return jsonify(d)


@app.post("/api/order/<token>/status")
def status(token):
  data = request.get_json(force=True)
  new = data.get("status")
  allowed = {"Received", "Packing", "Ready", "Collected", "Cancelled"}
  if new not in allowed:
    return jsonify(error="Invalid status"), 400
  con = db()
  if new == "Cancelled":
    r = con.execute("SELECT * FROM orders WHERE token=?", (token,)).fetchone()
    if r and r["status"] != "Cancelled":
      for x in json.loads(r["items_json"]):
        con.execute(
            "UPDATE items SET stock=stock+? WHERE id=?", (x["qty"], x["id"])
        )
  ready_at = (
      datetime.now().isoformat(timespec="seconds") if new == "Ready" else None
  )
  con.execute(
      "UPDATE orders SET status=?, ready_at=COALESCE(?,ready_at) WHERE token=?",
      (new, ready_at, token),
  )
  con.commit()
  con.close()
  return jsonify(ok=True)


@app.post("/api/order/<token>/payment")
def payment(token):
  p = request.get_json(force=True).get("payment", "Pending")
  if p not in {"Cash", "UPI", "Pending"}:
    return jsonify(error="Invalid payment"), 400
  con = db()
  con.execute("UPDATE orders SET payment=? WHERE token=?", (p, token))
  con.commit()
  con.close()
  return jsonify(ok=True)


@app.post("/api/item/<int:iid>")
def update_item(iid):
  data = request.get_json(force=True)
  con = db()
  if "stock" in data:
    con.execute(
        "UPDATE items SET stock=? WHERE id=?",
        (max(0, int(data["stock"])), iid),
    )
  if "price" in data:
    con.execute(
        "UPDATE items SET price=? WHERE id=?",
        (max(0, float(data["price"])), iid),
    )
  if "active" in data:
    con.execute(
        "UPDATE items SET active=? WHERE id=?",
        (1 if data["active"] else 0, iid),
    )
  con.commit()
  con.close()
  return jsonify(ok=True)


@app.post("/api/settings")
def settings():
  data = request.get_json(force=True)
  for k in ("discount_percent", "minutes_per_order", "upi_id", "stall_name"):
    if k in data:
      set_setting(k, data[k])
  return jsonify(ok=True)


@app.get("/api/summary")
def summary():
  con = db()
  today = datetime.now().strftime("%Y-%m-%d")
  s = con.execute(
      """SELECT COUNT(*) orders, COALESCE(SUM(total),0) sales,
                     COALESCE(SUM(CASE WHEN status='Ready' THEN 1 ELSE 0 END),0) ready
                     FROM orders WHERE created_at LIKE ?""",
      (today + "%",),
  ).fetchone()
  counts = con.execute(
      "SELECT status,COUNT(*) c FROM orders GROUP BY status"
  ).fetchall()
  stock = con.execute(
      "SELECT id,name,price,stock,active FROM items ORDER BY id"
  ).fetchall()
  con.close()
  return jsonify({
      "summary": dict(s),
      "counts": {r["status"]: r["c"] for r in counts},
      "items": [dict(r) for r in stock],
  })


if __name__ == "__main__":
  host = "0.0.0.0"
  port = 5000
  print("\nNEXTGEN FOOD STALL SYSTEM")
  print(f"Open on this computer: http://127.0.0.1:{port}/")
  print(
      "For phones on the same Wi-Fi/LAN, use this computer's IP address with"
      " :5000"
  )
  app.run(host=host, port=port, debug=False)
