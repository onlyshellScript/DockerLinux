from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
import copy
import data

app = Flask(__name__)
app.secret_key = "cambia-esta-clave-en-produccion"

# Estado en memoria (equivalente a SigosContext). Reemplazar por BD (SQLAlchemy) luego.
STATE = {
    "orders": copy.deepcopy(data.ORDERS),
    "technicians": data.TECHNICIANS,
    "materials": data.MATERIALS,
    "users": data.USERS,
    "notifications": copy.deepcopy(data.NOTIFICATIONS),
}
ZONES = ["Zona Norte", "Zona Sur", "Zona Centro", "Zona Industrial", "Zona Este", "Zona Oeste"]
INSTALL_TYPES = ["Instalación doméstica", "Instalación comercial", "Instalación industrial",
                 "Instalación hospitalaria", "Cambio de medidor", "Revisión de tuberías", "Cambio de quemadores"]
STATUS_CLASS = {"Pendiente": "pending", "Programada": "scheduled", "En proceso": "inprogress",
                "Completada": "completed", "Cancelada": "cancelled"}
PRIORITY_CLASS = {"Alta": "high", "Media": "medium", "Baja": "low"}

# Menú: (endpoint, etiqueta, icono, roles permitidos o None)
NAV = [
    ("dashboard", "Dashboard", "dashboard", None),
    ("orders", "Órdenes", "orders", None),
    ("technicians", "Técnicos", "tech", ["Administrador", "Coordinador"]),
    ("calendar", "Calendario", "calendar", None),
    ("materials", "Materiales", "materials", ["Administrador", "Coordinador"]),
    ("evidence", "Evidencias", "evidence", None),
    ("reports", "Reportes", "reports", ["Administrador", "Coordinador"]),
    ("users", "Usuarios", "users", ["Administrador"]),
]
NAV_BOTTOM = [
    ("notifications", "Notificaciones", "bell", None),
    ("settings", "Configuración", "settings", ["Administrador", "Coordinador"]),
    ("mobile", "Vista Técnico", "mobile", None),
]


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


@app.context_processor
def inject_globals():
    o, m, n = STATE["orders"], STATE["materials"], STATE["notifications"]
    user = session.get("user")
    role = user["role"] if user else None
    badges = {
        "orders": sum(1 for x in o if x["status"] in ("Pendiente", "Programada")),
        "materials": sum(1 for x in m if x["stockStatus"] in ("Bajo", "Crítico")),
        "notifications": sum(1 for x in n if not x["read"]),
    }
    ok = lambda item: item[3] is None or role in item[3]
    return dict(current_user=user, badges=badges,
                nav=[i for i in NAV if ok(i)], nav_bottom=[i for i in NAV_BOTTOM if ok(i)],
                STATUS_CLASS=STATUS_CLASS, PRIORITY_CLASS=PRIORITY_CLASS,
                unread=badges["notifications"], total_orders=len(o))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pwd = request.form.get("password", "")
        acc = next((a for a in data.DEMO_ACCOUNTS if a["email"].lower() == email and a["password"] == pwd), None)
        if acc:
            session["user"] = {k: acc[k] for k in ("name", "email", "role", "initials")}
            return redirect(url_for("orders"))
        error = "Correo o contraseña incorrectos."
    return render_template("login.html", error=error, accounts=data.DEMO_ACCOUNTS)


@app.route("/login/demo/<role>")
def login_demo(role):
    acc = next((a for a in data.DEMO_ACCOUNTS if a["role"] == role), None) or abort(404)
    session["user"] = {k: acc[k] for k in ("name", "email", "role", "initials")}
    return redirect(url_for("orders"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return redirect(url_for("orders"))


@app.route("/ordenes")
@login_required
def orders():
    user = session["user"]
    base = STATE["orders"]
    if user["role"] == "Técnico":
        base = [o for o in base if o["technician"] == user["name"]]
    q = request.args.get("q", "").strip().lower()
    status = request.args.get("status", "")
    tech = request.args.get("tech", "")
    zone = request.args.get("zone", "")
    filtered = [o for o in base
                if (not q or q in o["client"].lower() or q in o["id"].lower() or q in o["address"].lower())
                and (not status or o["status"] == status)
                and (not tech or o["technician"] == tech)
                and (not zone or o["zone"] == zone)]
    tabs = [("Todas", ""), ("Pendientes", "Pendiente"), ("Programadas", "Programada"),
            ("En proceso", "En proceso"), ("Completadas", "Completada")]
    tabs = [(label, st, len(base) if not st else sum(1 for o in base if o["status"] == st)) for label, st in tabs]
    return render_template("orders.html", orders=filtered, base_count=len(base), tabs=tabs,
                           f=dict(q=request.args.get("q", ""), status=status, tech=tech, zone=zone),
                           tech_names=[t["name"] for t in STATE["technicians"]], zones=ZONES,
                           install_types=INSTALL_TYPES, page_title="Órdenes de Servicio",
                           page_subtitle=f"{len(STATE['orders'])} órdenes registradas", active="orders")


@app.route("/ordenes/nueva", methods=["POST"])
@login_required
def create_order():
    f = request.form
    nums = [int("".join(c for c in o["id"] if c.isdigit()) or 0) for o in STATE["orders"]]
    oid = f"OS-{max(nums + [1000]) + 1:04d}"
    STATE["orders"].insert(0, dict(
        id=oid, client=f.get("client", ""), address=f.get("address", ""), clientPhone=f.get("phone", ""),
        zone=f.get("zone", "Zona Norte"), installationType=f.get("installationType", INSTALL_TYPES[0]),
        technician=f.get("technician") or "Sin asignar", visitDate=f.get("visitDate") or "Por definir",
        visitTime=f.get("visitTime", "09:00"), status="Pendiente", priority=f.get("priority", "Media"),
        notes=f.get("notes", "")))
    flash(f"Orden {oid} creada.")
    return redirect(url_for("order_detail", order_id=oid))


@app.route("/ordenes/<order_id>")
@login_required
def order_detail(order_id):
    order = next((o for o in STATE["orders"] if o["id"] == order_id), None) or abort(404)
    return render_template("pending.html", page_title=f"Orden {order['id']}", page_subtitle=order["client"],
                           active="orders", detail=order)


def _pending(title, active):
    return render_template("pending.html", page_title=title, page_subtitle="", active=active, detail=None)

@app.route("/dashboard")
@login_required
def dashboard(): return _pending("Dashboard", "dashboard")
@app.route("/tecnicos")
@login_required
def technicians(): return _pending("Técnicos", "technicians")
@app.route("/calendario")
@login_required
def calendar(): return _pending("Calendario", "calendar")
@app.route("/materiales")
@login_required
def materials(): return _pending("Materiales", "materials")
@app.route("/evidencias")
@login_required
def evidence(): return _pending("Evidencias", "evidence")
@app.route("/reportes")
@login_required
def reports(): return _pending("Reportes", "reports")
@app.route("/usuarios")
@login_required
def users(): return _pending("Usuarios", "users")
@app.route("/notificaciones")
@login_required
def notifications(): return _pending("Notificaciones", "notifications")
@app.route("/configuracion")
@login_required
def settings(): return _pending("Configuración", "settings")
@app.route("/campo")
@login_required
def mobile(): return _pending("Vista Técnico", "mobile")


if __name__ == "__main__":
    app.run(debug=True)
