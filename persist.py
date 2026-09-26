"""로컬 파일과 구글 시트에 목록·문구·명함을 저장합니다."""

from __future__ import annotations

import json
import sqlite3
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


def _secret(key: str, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def app_password() -> str:
    return str(_secret("app_password") or "").strip()


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


def load_sent_emails() -> dict:
    if not SENT_MAIL_FILE.exists():
        return {}
    try:
        data = json.loads(SENT_MAIL_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_sent_emails(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SENT_MAIL_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
        records = _load_local_records()
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


def sheets_enabled() -> bool:
    try:
        sa = _secret("gcp_service_account")
        sheets = _secret("sheets") or {}
        sid = ""
        if isinstance(sheets, dict):
            sid = str(sheets.get("spreadsheet_id") or "")
        if not sid:
            sid = str(_secret("spreadsheet_id") or "")
        return bool(sa and sid)
    except Exception:
        return False


def storage_label() -> str:
    return "구글 시트" if sheets_enabled() else "이 기기"


def _spreadsheet_id() -> str:
    sheets = _secret("sheets") or {}
    if isinstance(sheets, dict) and sheets.get("spreadsheet_id"):
        return str(sheets["spreadsheet_id"])
    return str(_secret("spreadsheet_id") or "")


@st.cache_resource
def _sheet_book():
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(_spreadsheet_id())


def _worksheet(title: str, headers: list[str]):
    book = _sheet_book()
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
    local = _load_local_records()
    if not sheets_enabled():
        return local
    try:
        remote = _load_sheet_records()
        if remote.empty and not local.empty:
            _save_sheet_records(local)
            return local
        return remote
    except Exception:
        return local


def save_records(df: pd.DataFrame) -> None:
    _save_local_records(df)
    if sheets_enabled():
        try:
            _save_sheet_records(df)
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
