from __future__ import annotations
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "jobhub_logistikk.db"
LOGO_DIR = STATIC_DIR / "uploads" / "logos"

STATIC_DIR.mkdir(exist_ok=True)
LOGO_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="JobHub Logistikk")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SystemIn(BaseModel):
    compact_top: bool
    show_top_cards: bool
    show_filter_area: bool
    show_followup_in_header: bool
    open_loads_by_default: bool
    show_next_available_first: bool
    load_header_color: str = Field(min_length=4)
    unassigned_header_color: str = Field(min_length=4)
    primary_button_color: str = Field(min_length=4)
    export_language: str
    unassigned_header_height: int = Field(ge=24, le=80)
    load_header_height: int = Field(ge=24, le=80)

class ClientIn(BaseModel):
    name: str
    company_name: str
    org_no: str
    email: str
    phone: str
    address: str
    post_place: str
    website: str
    language: str
    pdf_header: str
    pdf_footer: str

class SupplierIn(BaseModel):
    name: str
    ordered_by: str
    lead_weeks: int = Field(ge=0, le=520)
    default_tag: str
    max_orders_per_load: int = Field(ge=1, le=9999)
    delivery_text_no: str
    delivery_text_en: str
    auto_create_load: bool

def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def row_to_dict(row):
    return {k: row[k] for k in row.keys()}

def init_db() -> None:
    conn = connect()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS system_settings (
        id INTEGER PRIMARY KEY CHECK(id = 1),
        compact_top INTEGER NOT NULL DEFAULT 1,
        show_top_cards INTEGER NOT NULL DEFAULT 1,
        show_filter_area INTEGER NOT NULL DEFAULT 1,
        show_followup_in_header INTEGER NOT NULL DEFAULT 1,
        open_loads_by_default INTEGER NOT NULL DEFAULT 1,
        show_next_available_first INTEGER NOT NULL DEFAULT 0,
        load_header_color TEXT NOT NULL DEFAULT '#6b4028',
        unassigned_header_color TEXT NOT NULL DEFAULT '#ff1a00',
        primary_button_color TEXT NOT NULL DEFAULT '#f58220',
        export_language TEXT NOT NULL DEFAULT 'Norsk',
        unassigned_header_height INTEGER NOT NULL DEFAULT 36,
        load_header_height INTEGER NOT NULL DEFAULT 36,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        company_name TEXT NOT NULL DEFAULT '',
        org_no TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        address TEXT NOT NULL DEFAULT '',
        post_place TEXT NOT NULL DEFAULT '',
        website TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'Norsk',
        pdf_header TEXT NOT NULL DEFAULT '',
        pdf_footer TEXT NOT NULL DEFAULT '',
        logo_path TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        slug TEXT NOT NULL,
        name TEXT NOT NULL,
        ordered_by TEXT NOT NULL DEFAULT '',
        lead_weeks INTEGER NOT NULL DEFAULT 6,
        default_tag TEXT NOT NULL DEFAULT 'Ingen',
        max_orders_per_load INTEGER NOT NULL DEFAULT 3,
        delivery_text_no TEXT NOT NULL DEFAULT 'Levering',
        delivery_text_en TEXT NOT NULL DEFAULT 'Delivery',
        auto_create_load INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(client_id, slug)
    );
    """)
    if not cur.execute("SELECT 1 FROM system_settings WHERE id = 1").fetchone():
        cur.execute(
            "INSERT INTO system_settings VALUES (1,1,1,1,1,1,0,'#6b4028','#ff1a00','#f58220','Norsk',36,36,?)",
            (now_iso(),),
        )
    if cur.execute("SELECT COUNT(*) AS c FROM clients").fetchone()["c"] == 0:
        ts = now_iso()
        cur.execute(
            """
            INSERT INTO clients (
                slug,name,company_name,org_no,email,phone,address,post_place,website,language,pdf_header,pdf_footer,logo_path,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            ("tm","Traktor og Maskin AS","Traktor og Maskin AS","NO 925459399 MVA","tm@traktorogmaskin.no","38133000","Setesdalsveien 620","4619 MOSBY","www.traktorogmaskin.no","Norsk","Traktor og Maskin AS","",None,ts,ts),
        )
        client_id = cur.lastrowid
        cur.execute(
            """
            INSERT INTO suppliers (client_id,slug,name,ordered_by,lead_weeks,default_tag,max_orders_per_load,delivery_text_no,delivery_text_en,auto_create_load,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (client_id,"dolen","Dølen","Dølen Produkter AS",6,"Ingen",3,"Levering","Delivery",1,ts,ts),
        )
        cur.execute(
            """
            INSERT INTO suppliers (client_id,slug,name,ordered_by,lead_weeks,default_tag,max_orders_per_load,delivery_text_no,delivery_text_en,auto_create_load,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (client_id,"jpm","JPM","Traktor og Maskin AS",8,"Haster",4,"Levering","Delivery",1,ts,ts),
        )
    conn.commit()
    conn.close()

def bootstrap():
    conn = connect()
    cur = conn.cursor()
    system = row_to_dict(cur.execute("SELECT * FROM system_settings WHERE id = 1").fetchone())
    clients = []
    for client_row in cur.execute("SELECT * FROM clients ORDER BY name").fetchall():
        client = row_to_dict(client_row)
        client["suppliers"] = [row_to_dict(r) for r in cur.execute("SELECT * FROM suppliers WHERE client_id = ? ORDER BY name", (client["id"],)).fetchall()]
        clients.append(client)
    conn.close()
    return {"system": system, "clients": clients}

@app.on_event("startup")
def startup() -> None:
    init_db()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/api/bootstrap")
def api_bootstrap():
    return bootstrap()

@app.put("/api/system")
def put_system(payload: SystemIn):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
    UPDATE system_settings SET
      compact_top=?, show_top_cards=?, show_filter_area=?, show_followup_in_header=?,
      open_loads_by_default=?, show_next_available_first=?, load_header_color=?,
      unassigned_header_color=?, primary_button_color=?, export_language=?,
      unassigned_header_height=?, load_header_height=?, updated_at=?
    WHERE id=1
    """, (
        int(payload.compact_top), int(payload.show_top_cards), int(payload.show_filter_area),
        int(payload.show_followup_in_header), int(payload.open_loads_by_default),
        int(payload.show_next_available_first), payload.load_header_color,
        payload.unassigned_header_color, payload.primary_button_color,
        payload.export_language, payload.unassigned_header_height, payload.load_header_height, now_iso()
    ))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.put("/api/clients/{client_id}")
def put_client(client_id: int, payload: ClientIn):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
    UPDATE clients SET
      name=?, company_name=?, org_no=?, email=?, phone=?, address=?, post_place=?, website=?,
      language=?, pdf_header=?, pdf_footer=?, updated_at=?
    WHERE id=?
    """, (
        payload.name, payload.company_name, payload.org_no, payload.email, payload.phone,
        payload.address, payload.post_place, payload.website, payload.language,
        payload.pdf_header, payload.pdf_footer, now_iso(), client_id
    ))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Klient ikke funnet")
    conn.commit()
    conn.close()
    return {"ok": True}

@app.put("/api/suppliers/{supplier_id}")
def put_supplier(supplier_id: int, payload: SupplierIn):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
    UPDATE suppliers SET
      name=?, ordered_by=?, lead_weeks=?, default_tag=?, max_orders_per_load=?,
      delivery_text_no=?, delivery_text_en=?, auto_create_load=?, updated_at=?
    WHERE id=?
    """, (
        payload.name, payload.ordered_by, payload.lead_weeks, payload.default_tag,
        payload.max_orders_per_load, payload.delivery_text_no, payload.delivery_text_en,
        int(payload.auto_create_load), now_iso(), supplier_id
    ))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Leverandør ikke funnet")
    conn.commit()
    conn.close()
    return {"ok": True}

@app.post("/api/clients/{client_id}/logo")
def upload_logo(client_id: int, file: UploadFile = File(...)):
    suffix = Path(file.filename or "logo").suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
        raise HTTPException(status_code=400, detail="Ugyldig filtype for logo")
    target_dir = LOGO_DIR / str(client_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"logo{suffix}"
    with target.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    rel = f"/static/uploads/logos/{client_id}/{target.name}"
    conn = connect()
    cur = conn.cursor()
    cur.execute("UPDATE clients SET logo_path=?, updated_at=? WHERE id=?", (rel, now_iso(), client_id))
    conn.commit()
    conn.close()
    return {"ok": True, "logo_path": rel}

@app.delete("/api/clients/{client_id}/logo")
def delete_logo(client_id: int):
    conn = connect()
    cur = conn.cursor()
    row = cur.execute("SELECT logo_path FROM clients WHERE id=?", (client_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Klient ikke funnet")
    logo_path = row["logo_path"]
    if logo_path:
        fs = STATIC_DIR / logo_path.replace("/static/", "")
        if fs.exists():
            fs.unlink()
    cur.execute("UPDATE clients SET logo_path=NULL, updated_at=? WHERE id=?", (now_iso(), client_id))
    conn.commit()
    conn.close()
    return {"ok": True}

