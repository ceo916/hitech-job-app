"""로컬 파일과 구글 시트에 목록·문구·명함을 저장합니다."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"
DATA_FILE = DATA_DIR / "collected_jobs.csv"
DB_FILE = DATA_DIR / "hitech_jobs.db"
PHRASE_FILE = DATA_DIR / "phrases.json"
MAIL_SETTINGS_FILE = DATA_DIR / "mail_settings.json"
SHEETS_SETTINGS_FILE = DATA_DIR / "sheets_settings.json"
CARD_DIR = DATA_DIR / "card"
SENT_MAIL_FILE = DATA_DIR / "sent_emails.json"

COLUMNS = [
    "id",
    "등록일시",
    "구분",
    "현장명",
    "프로젝트",
    "협력사명",
    "담당자",
    "연락처",
    "이메일",
    "이미지",
    "원문",
    "카톡발송",
    "메일발송",
]

LEADS_SHEET = "leads"
PHRASES_SHEET = "phrases"
SENT_SHEET = "sent_mail"
SETTINGS_SHEET = "settings"


def _secret(key: str, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def parse_sheet_id(text: str) -> str:
    raw = (text or "").strip()
    if "/spreadsheets/d/" in raw:
        return raw.split("/spreadsheets/d/")[1].split("/")[0]
    return raw


def load_sheets_file() -> dict:
    if not SHEETS_SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SHEETS_SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_sheets_file(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SHEETS_SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _sa_info() -> dict:
    file = load_sheets_file()
    sa = file.get("gcp_service_account")
    if isinstance(sa, dict) and sa.get("client_email"):
        return sa
    try:
        sa = _secret("gcp_service_account")
        if sa:
            return dict(sa)
    except Exception:
        pass
    return {}


def _spreadsheet_id() -> str:
    file = load_sheets_file()
    sid = parse_sheet_id(str(file.get("spreadsheet_id") or ""))
    if sid:
        return sid
    sheets = _secret("sheets") or {}
    if isinstance(sheets, dict) and sheets.get("spreadsheet_id"):
        return parse_sheet_id(str(sheets.get("spreadsheet_id") or ""))
    return parse_sheet_id(str(_secret("spreadsheet_id") or ""))


def sheets_enabled() -> bool:
    return bool(_sa_info() and _spreadsheet_id())


def storage_label() -> str:
    return "공유 저장(구글 시트)" if sheets_enabled() else "이 기기만"


def save_sheet_connection(spreadsheet_id: str, service_account: dict) -> str:
    sid = parse_sheet_id(spreadsheet_id)
    if not sid:
        return "시트 주소 또는 아이디를 넣으세요."
    if not isinstance(service_account, dict) or not service_account.get("client_email"):
        return "서비스 계정 JSON이 올바르지 않습니다."
    current = load_sheets_file()
    current["spreadsheet_id"] = sid
    current["gcp_service_account"] = service_account
    save_sheets_file(current)
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    try:
        _worksheet(LEADS_SHEET, COLUMNS)
    except Exception as exc:
        return f"시트에 연결하지 못했습니다. 서비스 계정 이메일에 시트 편집 권한을 주세요. ({exc})"
    return ""


def app_password() -> str:
    pw = str(_secret("app_password") or "").strip()
    if pw:
        return pw
    file = load_sheets_file()
    pw = str(file.get("app_password") or "").strip()
    if pw:
        return pw
    if sheets_enabled():
        try:
            return str(_setting("app_password") or "").strip()
        except Exception:
            pass
    return ""


def save_app_password(password: str) -> None:
    current = load_sheets_file()
    current["app_password"] = (password or "").strip()
    save_sheets_file(current)
    if sheets_enabled():
        try:
            _save_setting("app_password", (password or "").strip())
        except Exception:
            pass


def load_mail_settings() -> dict:
    email = ""
    app_pw = ""
    try:
        gmail = _secret("gmail") or {}
        if isinstance(gmail, dict):
            email = str(gmail.get("email") or "").strip()
            app_pw = str(gmail.get("app_password") or "").strip()
    except Exception:
        pass
    if MAIL_SETTINGS_FILE.exists():
        try:
            data = json.loads(MAIL_SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                email = str(data.get("email") or email).strip()
                app_pw = str(data.get("app_password") or app_pw).strip()
        except Exception:
            pass
    if sheets_enabled():
        try:
            email = str(_setting("gmail_email") or email).strip() or email
            app_pw = str(_setting("gmail_app_password") or app_pw).strip() or app_pw
        except Exception:
            pass
    return {"email": email, "app_password": app_pw}


def save_mail_settings(email: str, app_pw: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MAIL_SETTINGS_FILE.write_text(
        json.dumps(
            {"email": (email or "").strip(), "app_password": (app_pw or "").strip()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if sheets_enabled():
        try:
            _save_setting("gmail_email", (email or "").strip())
            if (app_pw or "").strip():
                _save_setting("gmail_app_password", (app_pw or "").strip())
        except Exception:
            pass


def card_path() -> Path | None:
    if not CARD_DIR.exists():
        return None
    files = [p for p in CARD_DIR.iterdir() if p.is_file()]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def save_card(file) -> Path:
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    for old in CARD_DIR.iterdir():
        if old.is_file():
            old.unlink()
    suffix = Path(getattr(file, "name", "card.jpg")).suffix.lower() or ".jpg"
    if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
        suffix = ".jpg"
    path = CARD_DIR / f"namecard{suffix}"
    path.write_bytes(file.getvalue())
    return path


def clear_card() -> None:
    if not CARD_DIR.exists():
        return
    for old in CARD_DIR.iterdir():
        if old.is_file():
            old.unlink()


def norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _load_local_sent() -> dict:
    if not SENT_MAIL_FILE.exists():
        return {}
    try:
        data = json.loads(SENT_MAIL_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_local_sent(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SENT_MAIL_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_sheet_sent() -> dict:
    ws = _worksheet(SENT_SHEET, ["email", "at", "id", "회사"])
    out = {}
    for row in ws.get_all_records():
        key = norm_email(str(row.get("email") or ""))
        if not key:
            continue
        out[key] = {
            "at": str(row.get("at") or ""),
            "id": str(row.get("id") or ""),
            "회사": str(row.get("회사") or ""),
        }
    return out


def _save_sheet_sent(data: dict) -> None:
    ws = _worksheet(SENT_SHEET, ["email", "at", "id", "회사"])
    rows = [["email", "at", "id", "회사"]]
    for email, info in (data or {}).items():
        info = info if isinstance(info, dict) else {}
        rows.append([
            str(email),
            str(info.get("at") or ""),
            str(info.get("id") or ""),
            str(info.get("회사") or ""),
        ])
    ws.clear()
    ws.update(rows, "A1")


def load_sent_emails() -> dict:
    cached = _mem_get("sent", 8)
    if cached is not None:
        return dict(cached)
    data = _load_local_sent()
    if sheets_enabled():
        try:
            remote = _load_sheet_sent()
            data.update(remote)
            _save_local_sent(data)
        except Exception:
            pass
    _mem_set("sent", data)
    return dict(data)


def save_sent_emails(data: dict) -> None:
    _save_local_sent(data)
    _mem_set("sent", data)
    if sheets_enabled():
        try:
            _save_sheet_sent(data)
        except Exception:
            pass


def mark_email_sent(email: str, record_id: str = "", company: str = "", stamp: str = "") -> str:
    key = norm_email(email)
    stamp = stamp or datetime.now().strftime("%Y-%m-%d %H:%M")
    if not key:
        return stamp
    data = load_sent_emails()
    data[key] = {"at": stamp, "id": record_id or "", "회사": company or ""}
    save_sent_emails(data)
    return stamp


def sent_mail_info(email: str) -> dict | None:
    key = norm_email(email)
    if not key:
        return None
    data = load_sent_emails()
    if key in data and isinstance(data[key], dict):
        return data[key]
    try:
        records = load_records()
    except Exception:
        return None
    if records is None or records.empty:
        return None
    for _, row in records.iterrows():
        if norm_email(str(row.get("이메일") or "")) != key:
            continue
        stamp = str(row.get("메일발송") or "").strip()
        if not stamp:
            continue
        info = {"at": stamp, "id": str(row.get("id") or ""), "회사": str(row.get("협력사명") or "")}
        mark_email_sent(key, info["id"], info["회사"], stamp)
        return info
    return None


def send_partner_mail(to: str, subject: str, body: str) -> str:
    import mimetypes
    import smtplib
    from email.message import EmailMessage

    settings = load_mail_settings()
    sender = settings.get("email") or ""
    password = (settings.get("app_password") or "").replace(" ", "")
    to = (to or "").strip()
    if not sender or not password:
        return "보내는 Gmail과 앱 비밀번호를 먼저 저장하세요."
    if not to:
        return "받는 협력사 이메일이 없습니다."
    prior = sent_mail_info(to)
    if prior:
        when = prior.get("at") or ""
        return f"이미 {when}에 보낸 주소입니다. 같은 메일로 다시 보내지 않습니다."
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject or ""
    msg.set_content(body or "")
    card = card_path()
    if card and card.exists():
        mime, _ = mimetypes.guess_type(str(card))
        maintype, subtype = (mime or "image/jpeg").split("/", 1)
        msg.add_attachment(card.read_bytes(), maintype=maintype, subtype=subtype, filename=card.name)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
    except Exception as exc:
        return f"메일을 보내지 못했습니다. Gmail 주소와 앱 비밀번호를 확인하세요. ({exc})"
    mark_email_sent(to)
    return ""


@st.cache_resource
def _sheet_book(sid: str, sa_email: str):
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(_sa_info(), scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(sid)


def _worksheet(title: str, headers: list[str]):
    sa = _sa_info()
    book = _sheet_book(_spreadsheet_id(), str(sa.get("client_email") or ""))
    try:
        ws = book.worksheet(title)
    except Exception:
        ws = book.add_worksheet(title=title, rows=2000, cols=max(len(headers), 8))
        ws.update([headers], "A1")
        return ws
    existing = ws.row_values(1)
    if not existing:
        ws.update([headers], "A1")
    return ws


def _settings_map() -> dict:
    ws = _worksheet(SETTINGS_SHEET, ["key", "value"])
    rows = ws.get_all_records()
    out = {}
    for row in rows:
        key = str(row.get("key") or "").strip()
        if key:
            out[key] = str(row.get("value") or "")
    return out


def _setting(key: str) -> str:
    return _settings_map().get(key, "")


def _save_setting(key: str, value: str) -> None:
    data = _settings_map()
    data[key] = value
    ws = _worksheet(SETTINGS_SHEET, ["key", "value"])
    rows = [["key", "value"]] + [[k, data[k]] for k in data]
    ws.clear()
    ws.update(rows, "A1")


def merge_records(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    a = normalize_records(left)
    b = normalize_records(right)
    if a.empty:
        return b
    if b.empty:
        return a
    combined: dict[str, dict] = {}
    for src in (a, b):
        for _, row in src.iterrows():
            item = {c: str(row.get(c) or "") for c in COLUMNS}
            rid = item["id"]
            if rid not in combined:
                combined[rid] = item
                continue
            prev = combined[rid]
            for col in COLUMNS:
                old = prev.get(col) or ""
                new = item.get(col) or ""
                if col in ("메일발송", "카톡발송", "등록일시"):
                    prev[col] = max(old, new)
                elif new and (not old or len(new) > len(old)):
                    prev[col] = new
            combined[rid] = prev
    return normalize_records(pd.DataFrame(list(combined.values())))


def merge_phrases(left: dict, right: dict) -> dict:
    out = {"팀장": [], "협력사": []}
    for kind in ("팀장", "협력사"):
        by_id = {}
        for src in (left or {}, right or {}):
            for item in src.get(kind) or []:
                pid = str(item.get("id") or uuid.uuid4().hex[:10])
                by_id[pid] = dict(item)
                by_id[pid]["id"] = pid
        out[kind] = list(by_id.values())
    return out


def unify_all() -> str:
    if not sheets_enabled():
        return "구글 시트를 먼저 연결하세요."
    try:
        local_r = _load_local_records()
        remote_r = _load_sheet_records()
        merged_r = merge_records(local_r, remote_r)
        _save_local_records(merged_r)
        _save_sheet_records(merged_r)

        local_p = _load_local_phrases() or default_phrases()
        remote_p = _load_sheet_phrases() or {"팀장": [], "협력사": []}
        merged_p = merge_phrases(local_p, remote_p)
        _save_local_phrases(merged_p)
        _save_sheet_phrases(merged_p)

        local_s = _load_local_sent()
        remote_s = _load_sheet_sent()
        local_s.update(remote_s)
        _save_local_sent(local_s)
        _save_sheet_sent(local_s)
        mail = load_mail_settings()
        if mail.get("email"):
            _save_setting("gmail_email", mail.get("email") or "")
        if mail.get("app_password"):
            _save_setting("gmail_app_password", mail.get("app_password") or "")
        pw = app_password()
        if pw:
            _save_setting("app_password", pw)
        _mem_clear()
    except Exception as exc:
        return f"데이터를 합치지 못했습니다. ({exc})"
    return ""


def normalize_records(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNS)
    out = df.copy().fillna("")
    if "협력사명" not in out.columns and "회사명" in out.columns:
        out["협력사명"] = out["회사명"]
    if "구분" not in out.columns:
        out["구분"] = ""
    out["구분"] = out["구분"].replace({"기술인": "팀장", "업체": "협력사", "관리자": "협력사"})
    out.loc[~out["구분"].isin(["팀장", "협력사"]), "구분"] = "팀장"
    if "id" not in out.columns:
        out["id"] = [uuid.uuid4().hex[:12] for _ in range(len(out))]
    out.loc[out["id"].astype(str).isin(["", "nan"]), "id"] = [
        uuid.uuid4().hex[:12] for _ in range(len(out))
    ]
    for col in COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out[COLUMNS].astype(str)


_PHRASE_SEED: dict | None = None
_MEM = {}


def _mem_get(key: str, ttl: float):
    hit = _MEM.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    return None


def _mem_set(key: str, value) -> None:
    _MEM[key] = (time.time(), value)


def _mem_clear(*keys: str) -> None:
    if not keys:
        _MEM.clear()
        return
    for key in keys:
        _MEM.pop(key, None)


def set_phrase_seed(data: dict) -> None:
    global _PHRASE_SEED
    _PHRASE_SEED = data


def default_phrases() -> dict:
    if _PHRASE_SEED:
        return json.loads(json.dumps(_PHRASE_SEED))
    return {"팀장": [], "협력사": []}


def _load_local_records() -> pd.DataFrame:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS leads (" + ", ".join(f'"{c}" TEXT' for c in COLUMNS) + ")")
    try:
        db_df = normalize_records(pd.read_sql_query("SELECT * FROM leads", conn))
    except Exception:
        db_df = pd.DataFrame(columns=COLUMNS)
    csv_df = pd.DataFrame(columns=COLUMNS)
    if DATA_FILE.exists():
        try:
            csv_df = normalize_records(pd.read_csv(DATA_FILE, dtype=str, encoding="utf-8-sig"))
        except Exception:
            csv_df = pd.DataFrame(columns=COLUMNS)
    if db_df.empty and not csv_df.empty:
        db_df = csv_df
        db_df.to_sql("leads", conn, if_exists="replace", index=False)
        conn.commit()
    conn.close()
    return db_df


def _save_local_records(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    out = normalize_records(df)
    try:
        conn = sqlite3.connect(DB_FILE)
        out.to_sql("leads", conn, if_exists="replace", index=False)
        conn.commit()
        conn.close()
    except Exception:
        pass
    try:
        out.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
        out.to_csv(BACKUP_DIR / f"collected_jobs_{datetime.now().strftime('%Y%m%d')}.csv", index=False, encoding="utf-8-sig")
    except Exception:
        pass


def _load_sheet_records() -> pd.DataFrame:
    ws = _worksheet(LEADS_SHEET, COLUMNS)
    rows = ws.get_all_records()
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    return normalize_records(pd.DataFrame(rows))


def _save_sheet_records(df: pd.DataFrame) -> None:
    out = normalize_records(df)
    ws = _worksheet(LEADS_SHEET, COLUMNS)
    values = [COLUMNS] + out[COLUMNS].astype(str).values.tolist()
    ws.clear()
    ws.update(values, "A1")


def load_records() -> pd.DataFrame:
    cached = _mem_get("records", 8)
    if cached is not None:
        return cached.copy()
    local = _load_local_records()
    if not sheets_enabled():
        _mem_set("records", local)
        return local
    try:
        remote = _load_sheet_records()
        if remote.empty and not local.empty:
            _save_sheet_records(local)
            _mem_set("records", local)
            return local
        if not remote.empty:
            _save_local_records(remote)
            _mem_set("records", remote)
            return remote
        _mem_set("records", local)
        return local
    except Exception:
        _mem_set("records", local)
        return local


def save_records(df: pd.DataFrame) -> None:
    _save_local_records(df)
    _mem_clear("records")
    if sheets_enabled():
        try:
            _save_sheet_records(df)
            _mem_set("records", normalize_records(df))
        except Exception:
            pass


def _load_local_phrases() -> dict | None:
    if not PHRASE_FILE.exists():
        return None
    try:
        data = json.loads(PHRASE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "팀장" in data and "협력사" in data:
            return data
    except Exception:
        pass
    return None


def _save_local_phrases(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        PHRASE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _phrases_to_rows(data: dict) -> list[list[str]]:
    rows = [["대상", "id", "이름", "제목", "본문"]]
    for kind in ("팀장", "협력사"):
        for item in data.get(kind) or []:
            rows.append([
                kind,
                str(item.get("id") or ""),
                str(item.get("이름") or ""),
                str(item.get("제목") or ""),
                str(item.get("본문") or ""),
            ])
    return rows


def _rows_to_phrases(rows: list[dict]) -> dict:
    out = {"팀장": [], "협력사": []}
    for row in rows:
        kind = str(row.get("대상") or "")
        if kind not in out:
            continue
        out[kind].append({
            "id": str(row.get("id") or uuid.uuid4().hex[:10]),
            "이름": str(row.get("이름") or ""),
            "제목": str(row.get("제목") or ""),
            "본문": str(row.get("본문") or ""),
        })
    return out


def _load_sheet_phrases() -> dict | None:
    ws = _worksheet(PHRASES_SHEET, ["대상", "id", "이름", "제목", "본문"])
    rows = ws.get_all_records()
    if not rows:
        return None
    data = _rows_to_phrases(rows)
    if data["팀장"] or data["협력사"]:
        return data
    return None


def _save_sheet_phrases(data: dict) -> None:
    ws = _worksheet(PHRASES_SHEET, ["대상", "id", "이름", "제목", "본문"])
    ws.clear()
    ws.update(_phrases_to_rows(data), "A1")


def load_phrases() -> dict:
    local = _load_local_phrases()
    if sheets_enabled():
        try:
            remote = _load_sheet_phrases()
            if remote:
                return remote
            seed = local or default_phrases()
            _save_sheet_phrases(seed)
            return seed
        except Exception:
            pass
    if local:
        return local
    phrases = default_phrases()
    save_phrases(phrases)
    return phrases


def save_phrases(data: dict) -> None:
    _save_local_phrases(data)
    if sheets_enabled():
        try:
            _save_sheet_phrases(data)
        except Exception:
            pass


def cloud_secrets_toml() -> str:
    sa = _sa_info()
    sid = _spreadsheet_id()
    lines = []
    pw = str(load_sheets_file().get("app_password") or "").strip()
    if pw:
        lines.append(f"app_password = {json.dumps(pw, ensure_ascii=False)}")
    if sid:
        lines.append("[sheets]")
        lines.append(f"spreadsheet_id = {json.dumps(sid)}")
    if sa:
        lines.append("[gcp_service_account]")
        for key, value in sa.items():
            if key == "private_key":
                lines.append(f'private_key = """{value}"""')
            elif isinstance(value, str):
                lines.append(f"{key} = {json.dumps(value)}")
            else:
                lines.append(f"{key} = {json.dumps(value)}")
    return "\n".join(lines) + "\n"
