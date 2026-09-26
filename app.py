"""
하이테크잡스
문구·사진을 분석해 현장/프로젝트/협력사/연락처를 저장하고,
문구저장에서 만든 글로 팀장(카톡)·협력사(메일)에게 보냅니다.
"""

from __future__ import annotations

import json
import re
import uuid
import base64
from datetime import datetime
from html import escape
from pathlib import Path
import pandas as pd
import streamlit as st

import importlib
import persist

persist = importlib.reload(persist)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = persist.DATA_DIR
BACKUP_DIR = persist.BACKUP_DIR
IMAGE_DIR = DATA_DIR / "images"
DATA_FILE = persist.DATA_FILE
DB_FILE = persist.DB_FILE
PHRASE_FILE = persist.PHRASE_FILE
COLUMNS = persist.COLUMNS

SITE_AREAS = (
    "기흥", "화성", "평택", "이천", "용인", "청주", "온양", "천안",
    "탕정", "동탄", "아산", "수원", "음성", "우시",
)
SITE_AREA_RE = "|".join(SITE_AREAS)
FAB_CODE_RE = (
    r"(?:NRD\s*[-]?\s*[A-Za-z0-9]|NRD|P\s*\d+|M\s*\d{2}|FAB\s*\d+|팹\s*\d+|라인\s*\d+)"
)

KAKAO_TMPL = """팀장님 안녕하세요, 하이테크잡스입니다.

■ 현장: {현장명}
■ 프로젝트: {프로젝트}
■ 협력사: {협력사명}
■ 담당: {담당자} {연락처}

반도체 건설 구인·구직을 현장 기준으로 연결해 드립니다.
필요하시면 회신 주세요.
하이테크잡스
"""

MAIL_SUBJECT = "[하이테크잡스] {프로젝트} / {현장명} 협업 제안"
MAIL_BODY = """안녕하세요, {담당자}님.

하이테크잡스입니다.

{협력사명}의 {프로젝트}({현장명}) 건 관련하여
반도체 건설 인력·협력사 매칭 앱을 소개드립니다.

- 기술인(팀장)과 업체를 현장·공정 기준으로 연결
- 이미 연락한 번호는 중복으로 넣지 않음

관심 있으시면 이 메일에 회신 부탁드립니다.

감사합니다.
하이테크잡스
"""


def inject_pwa() -> None:
    icon_uri = ""
    icon = BASE_DIR / "static" / "icon.png"
    if icon.exists():
        icon_uri = "data:image/png;base64," + base64.b64encode(icon.read_bytes()).decode()
    icon_link = f'<link rel="apple-touch-icon" href="{icon_uri}">' if icon_uri else ""
    st.markdown(
        f"""
        <link rel="manifest" href="data:application/manifest+json,{{
          &quot;name&quot;:&quot;하이테크잡스&quot;,
          &quot;short_name&quot;:&quot;하이테크잡스&quot;,
          &quot;display&quot;:&quot;standalone&quot;,
          &quot;background_color&quot;:&quot;#F4F7FA&quot;,
          &quot;theme_color&quot;:&quot;#0E7C8B&quot;
        }}">
        {icon_link}
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-title" content="하이테크잡스">
        <meta name="apple-mobile-web-app-status-bar-style" content="default">
        <meta name="theme-color" content="#0E7C8B">
        """,
        unsafe_allow_html=True,
    )


def inject_css() -> None:
    st.markdown(
        """
        <style>
          html, body, [data-testid="stAppViewContainer"] {
            font-size: 16px;
            -webkit-text-size-adjust: 100%;
          }
          .block-container {
            padding-top: .7rem;
            padding-bottom: calc(2rem + env(safe-area-inset-bottom, 0px));
            padding-left: .9rem;
            padding-right: .9rem;
            max-width: 980px;
            overflow-x: hidden;
          }
          header[data-testid="stHeader"],
          [data-testid="stToolbar"],
          #MainMenu, footer { display: none !important; }
          .hero { font-size: 1.35rem; font-weight: 800; color: #0B3A5B; margin: 0 0 .15rem 0; }
          .sub { color: #4A6072; font-size: .95rem; line-height: 1.45; margin-bottom: .7rem; }
          label, [data-testid="stWidgetLabel"] p {
            font-size: 15px !important;
            font-weight: 650 !important;
          }
          [data-testid="stCaption"] { font-size: 14px !important; line-height: 1.4; }
          textarea, input, select {
            font-size: 16px !important;
            line-height: 1.4 !important;
          }
          [data-testid="stButton"],
          [data-testid="stLinkButton"],
          [data-testid="stDownloadButton"] { width: 100% !important; }
          [data-testid="stElementContainer"]:has([data-testid="stButton"]),
          [data-testid="stElementContainer"]:has([data-testid="stDownloadButton"]),
          [data-testid="stElementContainer"]:has([data-testid="stLinkButton"]) {
            width: 100% !important;
          }
          [data-testid="stButton"] button,
          [data-testid="stLinkButton"] a,
          [data-testid="stDownloadButton"] button {
            width: 100% !important;
            min-height: 48px !important;
            font-size: 16px !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
          }
          [data-testid="stTabs"] [role="tablist"] {
            gap: 6px;
            overflow: hidden;
            flex-wrap: wrap;
          }
          [data-testid="stTab"] {
            font-size: 15px !important;
            font-weight: 700 !important;
            min-height: 44px;
            padding: 8px 10px !important;
            border-radius: 12px !important;
            background: #E4EDF4 !important;
            display: flex !important;
            align-items: center;
            justify-content: center;
            border-bottom: 0 !important;
          }
          [data-testid="stTab"][aria-selected="true"],
          [data-testid="stTab"][data-selected="true"] {
            background: #0E7C8B !important;
            color: #fff !important;
          }
          [data-testid="stTab"] p { font-size: 15px !important; font-weight: 700 !important; color: inherit !important; }
          [data-testid="stRadio"] label {
            font-size: 16px !important;
            min-height: 42px;
            padding: 6px 10px !important;
          }
          [data-testid="stFileUploader"] section { padding: .7rem !important; }
          [data-testid="stDataFrame"] { overflow-x: auto; }
          iframe { border: 0 !important; }
          .ok, .warn {
            border-radius: 12px; padding: .75rem .9rem; font-size: 15px; line-height: 1.4;
          }
          .ok { background: #E8F8F5; color: #0E6655; }
          .warn { background: #FFF1F1; color: #922B21; }
          .job-card {
            background: #fff; border: 1px solid #d7e2ea; border-radius: 14px;
            padding: .85rem .95rem; margin-bottom: .65rem;
          }
          .job-card.picked { border-color: #1B6CA8; background: #F4F9FC; }
          .job-card b { color: #0B3A5B; font-size: 1.02rem; }
          .job-meta { color: #4A6072; font-size: 14px; line-height: 1.45; margin-top: .25rem; }
          @media (max-width: 640px) {
            .hero { font-size: 1.25rem; }
            .sub { font-size: .9rem; margin-bottom: .55rem; }
            .block-container { padding-left: .7rem; padding-right: .7rem; }
            [data-testid="stTabs"] [role="tablist"] {
              display: grid !important;
              grid-template-columns: 1fr 1fr;
              width: 100%;
            }
            [data-testid="stTab"] { width: 100% !important; }
            [data-testid="stHorizontalBlock"] {
              flex-direction: column !important;
              flex-wrap: wrap !important;
              gap: .45rem !important;
            }
            [data-testid="stColumn"] {
              width: 100% !important;
              min-width: 100% !important;
              flex: 1 1 100% !important;
            }
            [data-testid="stButton"] button,
            [data-testid="stLinkButton"] a,
            [data-testid="stDownloadButton"] button {
              min-height: 50px !important;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def copy_button(text: str, label: str) -> None:
    payload = json.dumps(text, ensure_ascii=False)
    label_js = json.dumps(label, ensure_ascii=False)
    st.iframe(
        f"""
        <button id="cbtn" style="width:100%;min-height:50px;border:0;border-radius:12px;
          background:#0B3A5B;color:#fff;font-size:16px;font-weight:700;cursor:pointer;">{label}</button>
        <script>
        const b=document.getElementById("cbtn");
        const t={payload}; const o={label_js};
        b.addEventListener("click",()=>{{
          const d=window.parent.document;
          const ta=d.createElement("textarea");
          ta.value=t; ta.style.position="fixed"; ta.style.left="-9999px";
          d.body.appendChild(ta); ta.select();
          try {{ d.execCommand("copy"); }} catch(e) {{}}
          d.body.removeChild(ta);
          b.innerText="복사됨";
          setTimeout(()=>b.innerText=o,1400);
        }});
        </script>
        """,
        height=58,
    )


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def format_phone(raw: str) -> str:
    d = digits_only(raw)
    if d.startswith("82") and len(d) >= 11:
        d = "0" + d[2:]
    if len(d) == 11 and d.startswith("01"):
        return f"{d[:3]}-{d[3:7]}-{d[7:]}"
    if len(d) == 10 and d.startswith("01"):
        return f"{d[:3]}-{d[3:6]}-{d[6:]}"
    if len(d) == 10 and d.startswith("02"):
        return f"{d[:2]}-{d[2:6]}-{d[6:]}"
    if len(d) == 10:
        return f"{d[:3]}-{d[3:6]}-{d[6:]}"
    return (raw or "").strip()


def extract_phones(text: str) -> list[str]:
    pattern = re.compile(
        r"(?:\+82[-.\s]?)?(?:0?1[016789]|0\d{1,2})[-.\s]?\d{3,4}[-.\s]?\d{4}"
    )
    found, seen = [], set()
    for match in pattern.findall(text or ""):
        formatted = format_phone(match)
        key = digits_only(formatted)
        if len(key) >= 9 and key not in seen:
            seen.add(key)
            found.append(formatted)
    return found


def extract_emails(text: str) -> list[str]:
    found = []
    for match in re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text or ""):
        if match.lower() not in {x.lower() for x in found}:
            found.append(match)
    return found


def labeled_value(text: str, labels: list[str]) -> str:
    for label in labels:
        match = re.search(rf"{label}\s*[:：]\s*(.+)", text or "")
        if match:
            value = re.split(r"[\n\r|/]", match.group(1).strip())[0]
            value = re.sub(r"\s{2,}", " ", value).strip(" -·•")
            if value:
                return value[:80]
    return ""


def guess_company(text: str) -> str:
    labeled = labeled_value(text, ["협력사명", "협력사", "회사명", "회사", "업체", "상호"])
    if labeled:
        return re.sub(r"(담당자|연락처|현장|전화|프로젝트).*$", "", labeled).strip()
    corp = re.search(
        r"((?:주식회사|\(주\)|㈜)\s*[가-힣A-Za-z0-9]+|"
        r"[가-힣A-Za-z0-9]{2,20}(?:건설|플랜트|엔지니어링|산업|테크|이엔씨|ENC|엔씨))",
        text or "",
    )
    return corp.group(1).strip() if corp else ""


def tidy_site_name(raw: str) -> str:
    s = re.sub(r"\s+", " ", raw or "").strip(" /-|.,")
    s = re.sub(
        r"NRD\s*[-]?\s*([A-Za-z0-9])",
        lambda m: "NRD-" + m.group(1).upper(),
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"(?<![A-Z])NRD(?!-)", "NRD", s, flags=re.IGNORECASE)
    s = re.sub(r"\bP\s*(\d+)\b", r"P\1", s, flags=re.IGNORECASE)
    s = re.sub(r"\bM\s*(\d{2})\b", r"M\1", s, flags=re.IGNORECASE)
    s = re.sub(r"([가-힣])(NRD|P\d|M\d|FAB)", r"\1 \2", s)
    return s[:80]


def guess_site(text: str) -> str:
    labeled = labeled_value(text, ["현장명", "현장"])
    if labeled:
        return tidy_site_name(re.sub(r"(담당자|연락처|회사|전화|프로젝트|협력).*$", "", labeled))
    patterns = [
        rf"((?:삼성전자|삼성|SK하이닉스|하이닉스)?\s*(?:{SITE_AREA_RE})\s*(?:캠퍼스|현장)?\s*{FAB_CODE_RE})",
        rf"(?<![A-Za-z])({FAB_CODE_RE})",
        r"((?:삼성전자|삼성|SK하이닉스|하이닉스)(?:[^\n]{0,16}?)(?:현장|캠퍼스|팹|FAB|P\d+|M\d{2}))",
        rf"((?:{SITE_AREA_RE})\s*(?:캠퍼스|현장))",
        r"((?:삼성전자|SK하이닉스|하이닉스)\s*[가-힣A-Za-z0-9]*)",
    ]
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        if not match:
            continue
        found = tidy_site_name(match.group(1))
        if index == 1 and re.search(r"NRD", found, flags=re.IGNORECASE) and "기흥" not in found:
            found = f"기흥 {found}"
        if found:
            return found
    return ""


def guess_project(text: str, site: str) -> str:
    labeled = labeled_value(text, ["프로젝트명", "프로젝트", "공사명", "사업명"])
    if labeled:
        return tidy_site_name(re.sub(r"(담당자|연락처|회사|전화|현장|협력).*$", "", labeled))
    return site


def guess_contact_name(text: str) -> str:
    labeled = labeled_value(text, ["담당자", "담당", "연락처 담당"])
    if labeled:
        name = re.split(r"\d", labeled)[0]
        name = re.sub(r"(연락처|전화|휴대폰|회사|현장).*$", "", name)
        cleaned = name.strip(" :：/-")[:20]
        if cleaned:
            return cleaned
    loose = re.search(r"담당자?\s+([가-힣]{2,8})", text or "")
    if loose:
        return re.sub(r"(연락처|전화|휴대폰)$", "", loose.group(1)).strip()[:20]
    skip = {"현장", "공사", "관리", "안전", "품질", "공무", "배관", "용접", "전기", "기계"}
    for match in re.finditer(r"([가-힣]{1,4})\s*(과장|차장|부장|소장|팀장|대리|사원|대표)", text or ""):
        if match.group(1) not in skip:
            return f"{match.group(1)}{match.group(2)}"
    return ""


def guess_kind(text: str) -> str:
    compact = (text or "").replace(" ", "")
    company_hits = sum(
        1 for w in ("현장소장", "관리자", "공무", "공사팀장", "현장대리인", "협력사") if w in compact
    )
    leader_hits = sum(
        1 for w in ("기술인", "기능공", "배관", "반장", "팀장", "용접", "크린룸", "클린룸") if w in compact
    )
    if company_hits > leader_hits:
        return "협력사"
    return "팀장"


def parse_source(text: str) -> dict:
    phones = extract_phones(text)
    emails = extract_emails(text)
    site = guess_site(text)
    return {
        "현장명": site,
        "프로젝트": guess_project(text, site),
        "협력사명": guess_company(text),
        "담당자": guess_contact_name(text),
        "연락처": phones[0] if phones else "",
        "이메일": emails[0] if emails else "",
        "구분": guess_kind(text),
        "원문": (text or "").strip(),
    }


def ocr_image(path: Path) -> str:
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
    except Exception:
        return ""
    try:
        from winocr import recognize_pil
        result = recognize_pil(img, "ko")
        if isinstance(result, dict):
            return str(result.get("text") or "")
        return str(result or "")
    except Exception:
        pass
    try:
        import pytesseract
        return pytesseract.image_to_string(img, lang="kor+eng")
    except Exception:
        return ""


def save_upload(file) -> Path:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(getattr(file, "name", "photo.jpg")).suffix or ".jpg"
    path = IMAGE_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{suffix}"
    path.write_bytes(file.getvalue())
    return path


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    return persist.normalize_records(df)


def load_records() -> pd.DataFrame:
    return persist.load_records()


def save_records(df: pd.DataFrame) -> None:
    persist.save_records(df)


def find_duplicate(phone: str, email: str, df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.iloc[0:0]
    mask = pd.Series(False, index=df.index)
    phone_key = digits_only(phone)
    mail_key = (email or "").strip().lower()
    if phone_key:
        mask = mask | (df["연락처"].map(digits_only) == phone_key)
    if mail_key:
        mask = mask | (df["이메일"].str.strip().str.lower() == mail_key)
    return df[mask]


def fill(template: str, row: dict) -> str:
    keys = {
        "현장명": row.get("현장명") or "-",
        "프로젝트": row.get("프로젝트") or "-",
        "협력사명": row.get("협력사명") or "-",
        "담당자": row.get("담당자") or "담당자",
        "연락처": row.get("연락처") or "-",
        "이메일": row.get("이메일") or "",
    }
    text = template or ""
    for k, v in keys.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def default_phrases() -> dict:
    seed = {
        "팀장": [
            {
                "id": "kakao_default",
                "이름": "기본 팀장 카톡",
                "제목": "",
                "본문": KAKAO_TMPL.strip(),
            }
        ],
        "협력사": [
            {
                "id": "mail_default",
                "이름": "기본 협력사 메일",
                "제목": MAIL_SUBJECT,
                "본문": MAIL_BODY.strip(),
            }
        ],
    }
    persist.set_phrase_seed(seed)
    return seed


def load_phrases() -> dict:
    persist.set_phrase_seed(default_phrases())
    return persist.load_phrases()


def save_phrases(data: dict) -> None:
    persist.save_phrases(data)


def init_state() -> None:
    defaults = {
        "raw_text": "",
        "field_kind": "팀장",
        "field_site": "",
        "field_project": "",
        "field_company": "",
        "field_person": "",
        "field_phone": "",
        "field_email": "",
        "field_source": "",
        "image_paths": [],
        "selected_id": "",
        "ocr_note": "",
        "save_msg": "",
        "reset_form": False,
        "upload_nonce": 0,
        "pending_mailto": "",
        "unlocked": False,
        "phrase_edit_id": "",
        "phrase_delete_id": "",
        "phrase_kind_prev": "팀장",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if st.session_state.field_kind not in ("팀장", "협력사"):
        st.session_state.field_kind = "팀장"
    if st.session_state.reset_form:
        st.session_state.raw_text = ""
        st.session_state.field_kind = "팀장"
        st.session_state.field_site = ""
        st.session_state.field_project = ""
        st.session_state.field_company = ""
        st.session_state.field_person = ""
        st.session_state.field_phone = ""
        st.session_state.field_email = ""
        st.session_state.field_source = ""
        st.session_state.image_paths = []
        st.session_state.ocr_note = ""
        st.session_state.upload_nonce = int(st.session_state.get("upload_nonce") or 0) + 1
        st.session_state.reset_form = False


def apply_parse(data: dict) -> None:
    st.session_state.field_kind = data.get("구분") or "팀장"
    st.session_state.field_site = data.get("현장명", "")
    st.session_state.field_project = data.get("프로젝트", "")
    st.session_state.field_company = data.get("협력사명", "")
    st.session_state.field_person = data.get("담당자", "")
    st.session_state.field_phone = data.get("연락처", "")
    st.session_state.field_email = data.get("이메일", "")
    st.session_state.field_source = data.get("원문", "")
    st.session_state.save_msg = ""


def current_fields() -> dict:
    phone = (st.session_state.get("field_phone") or "").strip()
    kind = st.session_state.get("field_kind") or "팀장"
    if kind not in ("팀장", "협력사"):
        kind = "팀장"
    return {
        "구분": kind,
        "현장명": (st.session_state.get("field_site") or "").strip(),
        "프로젝트": (st.session_state.get("field_project") or "").strip(),
        "협력사명": (st.session_state.get("field_company") or "").strip(),
        "담당자": (st.session_state.get("field_person") or "").strip(),
        "연락처": format_phone(phone) if phone else "",
        "이메일": (st.session_state.get("field_email") or "").strip(),
        "원문": (st.session_state.get("field_source") or st.session_state.get("raw_text") or "").strip(),
        "이미지": "|".join(st.session_state.get("image_paths") or []),
    }


def merge_grid_edits(all_records: pd.DataFrame, edited: pd.DataFrame) -> pd.DataFrame:
    if edited.empty or "id" not in edited.columns:
        return all_records
    out = all_records.copy()
    for _, row in edited.iterrows():
        rid = str(row.get("id") or "")
        if not rid:
            continue
        mask = out["id"] == rid
        for col in edited.columns:
            if col in ("선택", "메일발송", "카톡발송") or col not in out.columns:
                continue
            out.loc[mask, col] = str(row.get(col) or "")
    return out


def is_phone() -> bool:
    try:
        ua = str(st.context.headers.get("User-Agent") or "").lower()
    except Exception:
        ua = ""
    return any(token in ua for token in ("iphone", "android", "mobile", "ipad"))


def require_login() -> bool:
    password = persist.app_password()
    if not password:
        return True
    if st.session_state.get("unlocked"):
        return True
    st.markdown('<p class="hero" style="margin-top:2rem;">하이테크잡스</p>', unsafe_allow_html=True)
    st.caption("비밀번호를 입력하면 들어갑니다.")
    st.text_input("비밀번호", type="password", key="login_pw")
    if st.button("들어가기", type="primary"):
        if (st.session_state.get("login_pw") or "") == password:
            st.session_state.unlocked = True
            st.rerun()
        st.error("비밀번호가 맞지 않습니다.")
    return False


def render_backup_bar(records: pd.DataFrame) -> None:
    with st.expander("백업 / 복원"):
        st.caption(f"지금 저장 위치: {persist.storage_label()}. 클라우드에서는 가끔 목록이 비워질 수 있으니 백업을 받아 두세요.")
        st.download_button(
            "전체 목록 CSV 받기",
            data=records.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
            file_name=f"hitech_backup_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            width="stretch",
            key="dl_all_backup",
        )
        uploaded = st.file_uploader("백업 CSV로 복원", type=["csv"], key="restore_csv")
        if uploaded is not None and st.button("이 파일로 목록 바꾸기", key="do_restore"):
            try:
                incoming = persist.normalize_records(pd.read_csv(uploaded, dtype=str, encoding="utf-8-sig"))
            except Exception:
                incoming = persist.normalize_records(pd.read_csv(uploaded, dtype=str))
            save_records(incoming)
            st.success("백업을 넣었습니다.")
            st.rerun()


def render_card_list(subset: pd.DataFrame, kind: str) -> dict | None:
    selected = None
    for _, row in subset.iloc[::-1].iterrows():
        item = row.to_dict()
        rid = str(item.get("id") or "")
        title = escape(str(item.get("현장명") or item.get("협력사명") or "이름 없음"))
        sent = already_sent_mail(item) if kind == "협력사" else ""
        extra = f" · 전송됨 {escape(sent)}" if sent else ""
        project = escape(str(item.get("프로젝트") or "-"))
        company = escape(str(item.get("협력사명") or "-"))
        person = escape(str(item.get("담당자") or ""))
        phone = escape(str(item.get("연락처") or ""))
        email = escape(str(item.get("이메일") or ""))
        st.markdown(
            f"<div class='job-card'><b>{title}</b>"
            f"<div class='job-meta'>{project} · {company}<br>"
            f"{person} {phone} {email}{extra}</div></div>",
            unsafe_allow_html=True,
        )
        picked = st.checkbox("이 건 보내기", key=f"card_{kind}_{rid}")
        if picked and selected is None:
            st.session_state.selected_id = rid
            selected = item
    return selected


def mail_sent_at(row: dict | None) -> str:
    return already_sent_mail(row)


def already_sent_mail(row: dict | None) -> str:
    if not row:
        return ""
    own = str(row.get("메일발송") or "").strip()
    info = persist.sent_mail_info(str(row.get("이메일") or ""))
    if info:
        return str(info.get("at") or own or "보냄")
    return own


def mark_mail_sent(record_id: str, email: str = "", company: str = "") -> None:
    latest = load_records()
    stamp = persist.mark_email_sent(email, record_id, company)
    match_id = latest["id"].astype(str) == str(record_id)
    key = persist.norm_email(email)
    if key:
        match_id = match_id | latest["이메일"].map(persist.norm_email).eq(key)
    latest.loc[match_id, "메일발송"] = stamp
    save_records(latest)
    st.session_state.pop("grid_협력사", None)


def render_sender_settings() -> dict:
    settings = persist.load_mail_settings()
    current = settings.get("email") or ""
    with st.expander("보내는 메일 바꾸기", expanded=not current):
        st.caption("Gmail 로그인 비밀번호가 아니라, Google 계정의 앱 비밀번호 16자리를 넣습니다.")
        email = st.text_input("보내는 Gmail", value=current, key="sender_email")
        app_pw = st.text_input("Gmail 앱 비밀번호", type="password", key="sender_app_pw")
        if st.button("보내는 메일 저장", key="save_sender"):
            keep_pw = app_pw.strip() or (settings.get("app_password") or "")
            if not email.strip() or not keep_pw:
                st.error("Gmail 주소와 앱 비밀번호를 입력하세요.")
            else:
                persist.save_mail_settings(email.strip(), keep_pw)
                st.success("보내는 메일을 저장했습니다.")
                st.rerun()
        if current:
            st.caption(f"지금 보내는 주소: {current}")
    return persist.load_mail_settings()


def render_namecard(kind: str) -> None:
    st.markdown("##### 내 명함")
    card = persist.card_path()
    if card and card.exists():
        st.image(str(card), caption="저장한 명함", width="stretch")
        st.download_button(
            "명함 사진 받기",
            data=card.read_bytes(),
            file_name=card.name,
            mime="image/jpeg" if card.suffix.lower() in {".jpg", ".jpeg"} else "image/png",
            key=f"dl_card_{kind}",
            width="stretch",
        )
        if st.button("명함 지우기", key=f"clear_card_{kind}"):
            persist.clear_card()
            st.rerun()
    uploaded = st.file_uploader(
        "명함 사진 넣기",
        type=["png", "jpg", "jpeg", "webp"],
        key=f"namecard_upload_{kind}",
    )
    if uploaded is not None and st.button("이 명함 저장", key=f"save_card_{kind}"):
        persist.save_card(uploaded)
        st.success("명함을 저장했습니다. 협력사 메일에 같이 첨부됩니다.")
        st.rerun()
    if persist.card_path():
        st.caption("협력사 메일을 보내면 명함이 첨부됩니다. 팀장 카톡은 자동으로 사진을 넣을 수 없어, 카톡에서 직접 보내면 됩니다.")
    else:
        st.caption("명함을 넣어 두면 협력사 메일에 같이 나갑니다.")


def render_phrase_list(phrases: list, kind: str) -> dict:
    labels = [str(p.get("이름") or "이름 없음") for p in phrases]
    pick_i = st.radio("쓸 문구", list(range(len(phrases))), format_func=lambda i: labels[i], key=f"phrase_idx_{kind}")
    st.markdown("**저장된 문구**")
    for i, phrase in enumerate(phrases):
        title = escape(str(phrase.get("이름") or "이름 없음"))
        subject = escape(str(phrase.get("제목") or ""))
        body = escape(str(phrase.get("본문") or "")).replace("\n", "<br>")
        mark = " · 선택됨" if i == pick_i else ""
        picked = " picked" if i == pick_i else ""
        extra = f"<div class='job-meta'>제목: {subject}</div>" if subject else ""
        st.markdown(
            f"<div class='job-card{picked}'><b>{title}{mark}</b>{extra}"
            f"<div class='job-meta'>{body}</div></div>",
            unsafe_allow_html=True,
        )
    return phrases[pick_i]


def render_send_bar(selected: dict | None, kind: str) -> None:
    phrases = load_phrases().get(kind) or []
    st.markdown("##### 전송")
    if not phrases:
        st.warning("문구저장 탭에서 먼저 문구를 만드세요.")
        render_namecard(kind)
        if kind == "협력사":
            render_sender_settings()
        return
    tmpl = render_phrase_list(phrases, kind)
    render_namecard(kind)
    if kind == "협력사":
        render_sender_settings()
    if not selected:
        st.caption("위에서 한 건을 고르면 미리보기에 현장·협력사가 채워집니다.")
        return
    body = fill(str(tmpl.get("본문") or ""), selected)
    if kind == "팀장":
        st.text_area("카톡 미리보기", value=body, height=160, disabled=True, key="kakao_preview")
        copy_button(body, "카톡 문구 복사")
        st.link_button("카카오톡 열기", "kakaotalk://", width="stretch")
        if persist.card_path():
            st.caption("카톡이 열리면 저장한 명함 사진을 직접 첨부해 주세요. 카톡은 자동 전송이 되지 않습니다.")
        return
    subject = fill(str(tmpl.get("제목") or ""), selected)
    sent_at = already_sent_mail(selected)
    st.text_input("메일 제목 미리보기", value=subject, disabled=True, key="mail_sub_preview")
    st.text_area("메일 미리보기", value=body, height=150, disabled=True, key="mail_body_preview")
    if sent_at:
        st.markdown(
            f"<div class='ok'>이미 이 주소로 보낸 메일입니다. ({sent_at}) 같은 메일로 다시 보낼 수 없습니다.</div>",
            unsafe_allow_html=True,
        )
        return
    to = str(selected.get("이메일") or "").strip()
    sender = persist.load_mail_settings()
    can_send = bool(to and sender.get("email") and sender.get("app_password"))
    attach_note = "명함 포함" if persist.card_path() else "명함 없음"
    if st.button(f"메일 보내기 ({attach_note})", type="primary", disabled=not can_send, key="send_mail_btn"):
        if persist.sent_mail_info(to):
            st.error("이미 이 주소로 보낸 메일입니다. 다시 보내지 않습니다.")
            st.rerun()
        err = persist.send_partner_mail(to, subject, body)
        if err:
            st.error(err)
        else:
            mark_mail_sent(str(selected.get("id") or ""), to, str(selected.get("협력사명") or ""))
            extra = " 명함도 첨부했습니다." if persist.card_path() else ""
            st.success(f"{sender.get('email')} 에서 보냈습니다.{extra}")
            st.rerun()
    if not sender.get("email") or not sender.get("app_password"):
        st.caption("위에서 보내는 Gmail을 저장하면 여기서 바로 나갑니다.")
    elif not to:
        st.caption("이메일이 없으면 표에서 이메일 칸을 채운 뒤 「표 저장」을 누르세요.")


def render_excel_tab(records: pd.DataFrame, kind: str) -> None:
    subset = records[records["구분"] == kind].copy()
    selected = None
    st.caption(f"분류하기에서 「{kind}」로 저장한 목록입니다. 전송 문구는 문구저장 탭에서 만든 것을 씁니다.")
    default_view = "카드" if is_phone() else "표"
    view = st.radio("보기", options=["카드", "표"], index=0 if default_view == "카드" else 1, horizontal=True, key=f"view_{kind}")
    if subset.empty:
        st.info(f"아직 {kind} 자료가 없습니다. 분류하기 탭에서 구분을 {kind}으로 저장하세요.")
    elif view == "카드":
        selected = render_card_list(subset, kind)
        if selected is None and st.session_state.selected_id:
            hit = subset[subset["id"] == st.session_state.selected_id]
            if not hit.empty:
                selected = hit.iloc[0].to_dict()
    else:
        show_cols = ["선택", "등록일시", "현장명", "프로젝트", "협력사명", "담당자", "연락처"]
        if kind == "협력사":
            show_cols.extend(["이메일", "메일발송"])
        show_cols.append("id")
        grid = subset.copy()
        grid.insert(0, "선택", False)
        keep = [c for c in show_cols if c in grid.columns]
        edited = st.data_editor(
            grid[keep].iloc[::-1],
            width="stretch",
            hide_index=True,
            num_rows="fixed",
            key=f"grid_{kind}",
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", width="small"),
                "메일발송": st.column_config.TextColumn("메일발송", disabled=True, width="medium"),
                "id": st.column_config.TextColumn("id", disabled=True, width="small"),
            },
        )
        b1, b2 = st.columns(2)
        with b1:
            if st.button("표 저장", key=f"save_{kind}", type="primary"):
                latest = load_records()
                save_records(merge_grid_edits(latest, edited.drop(columns=["선택"], errors="ignore")))
                st.success("표 내용을 저장했습니다.")
                st.rerun()
        with b2:
            st.download_button(
                f"{kind} CSV",
                data=subset.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                file_name=f"hitech_{kind}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width="stretch",
                key=f"dl_{kind}",
            )
        picked = edited[edited["선택"].fillna(False).astype(bool)] if not edited.empty else edited.iloc[0:0]
        if not picked.empty:
            st.session_state.selected_id = str(picked.iloc[0]["id"])
            selected = picked.iloc[0].to_dict()
        elif st.session_state.selected_id:
            hit = subset[subset["id"] == st.session_state.selected_id]
            if not hit.empty:
                selected = hit.iloc[0].to_dict()
        if selected:
            full = records[records["id"].astype(str) == str(selected.get("id") or "")]
            if not full.empty:
                merged = full.iloc[0].to_dict()
                sent = str(merged.get("메일발송") or "").strip()
                merged.update({k: selected.get(k) for k in selected if k != "선택"})
                if sent:
                    merged["메일발송"] = sent
                selected = merged
    render_send_bar(selected, kind)


def render_phrase_tab() -> None:
    st.caption(
        "여기서 만든 문구가 팀장 카톡·협력사 메일에 쓰입니다. "
        "{현장명} {프로젝트} {협력사명} {담당자} {연락처} {이메일} 을 넣으면 전송할 때 자동으로 바뀝니다. "
        "아래 목록에서 수정하거나 지울 수 있습니다."
    )
    phrases = load_phrases()
    kind = st.radio("문구 대상", options=["팀장", "협력사"], horizontal=True, key="phrase_kind")
    if st.session_state.get("phrase_kind_prev") != kind:
        st.session_state.phrase_edit_id = ""
        st.session_state.phrase_delete_id = ""
        st.session_state.phrase_kind_prev = kind
    items = list(phrases.get(kind) or [])
    edit_id = str(st.session_state.get("phrase_edit_id") or "")
    current = next((dict(p) for p in items if str(p.get("id") or "") == edit_id), None)
    if edit_id and current is None:
        st.session_state.phrase_edit_id = ""
        edit_id = ""
    if current is None:
        current = {"id": "", "이름": "", "제목": "", "본문": ""}

    st.markdown("**저장된 문구**")
    if not items:
        st.info("저장된 문구가 없습니다. 아래에서 새 문구를 만드세요.")
    for phrase in items:
        pid = str(phrase.get("id") or "")
        title = escape(str(phrase.get("이름") or "이름 없음"))
        subject_txt = escape(str(phrase.get("제목") or ""))
        body_txt = escape(str(phrase.get("본문") or "")).replace("\n", "<br>")
        editing = " picked" if pid and pid == edit_id else ""
        extra = f"<div class='job-meta'>제목: {subject_txt}</div>" if subject_txt else ""
        st.markdown(
            f"<div class='job-card{editing}'><b>{title}</b>{extra}"
            f"<div class='job-meta'>{body_txt}</div></div>",
            unsafe_allow_html=True,
        )
        b1, b2 = st.columns(2)
        with b1:
            if st.button("수정", key=f"edit_{kind}_{pid}", width="stretch"):
                st.session_state.phrase_edit_id = pid
                st.session_state.phrase_delete_id = ""
                st.rerun()
        with b2:
            if st.session_state.get("phrase_delete_id") == pid:
                if st.button("정말 지우기", key=f"delok_{kind}_{pid}", type="primary", width="stretch"):
                    phrases[kind] = [p for p in items if str(p.get("id") or "") != pid]
                    save_phrases(phrases)
                    if st.session_state.phrase_edit_id == pid:
                        st.session_state.phrase_edit_id = ""
                    st.session_state.phrase_delete_id = ""
                    st.success("문구를 지웠습니다.")
                    st.rerun()
            elif st.button("삭제", key=f"del_{kind}_{pid}", width="stretch"):
                st.session_state.phrase_delete_id = pid
                st.rerun()
        if st.session_state.get("phrase_delete_id") == pid:
            c1, c2 = st.columns(2)
            with c1:
                st.caption("한 번 더 누르면 지워집니다.")
            with c2:
                if st.button("삭제 취소", key=f"delno_{kind}_{pid}", width="stretch"):
                    st.session_state.phrase_delete_id = ""
                    st.rerun()

    st.markdown("##### 새 문구" if not edit_id else "##### 문구 수정")
    form_key = edit_id or "new"
    name = st.text_input("문구 이름", value=current.get("이름") or "", key=f"pname_{kind}_{form_key}")
    subject = ""
    if kind == "협력사":
        subject = st.text_input(
            "메일 제목",
            value=current.get("제목") or "",
            key=f"psub_{kind}_{form_key}",
        )
    body = st.text_area(
        "본문",
        value=current.get("본문") or "",
        height=220,
        key=f"pbody_{kind}_{form_key}",
        placeholder="예: 팀장님 안녕하세요. {현장명} / {프로젝트} 건 공유드립니다.",
    )
    s1, s2 = st.columns(2)
    with s1:
        save_label = "수정 저장" if edit_id else "새 문구 저장"
        if st.button(save_label, type="primary", width="stretch"):
            if not name.strip() or not body.strip():
                st.error("이름과 본문을 입력하세요.")
            else:
                row = {
                    "id": current.get("id") or uuid.uuid4().hex[:10],
                    "이름": name.strip(),
                    "제목": subject.strip() if kind == "협력사" else "",
                    "본문": body.strip(),
                }
                if edit_id:
                    items = [row if str(p.get("id") or "") == edit_id else p for p in items]
                else:
                    items.append(row)
                phrases[kind] = items
                save_phrases(phrases)
                st.session_state.phrase_edit_id = ""
                st.session_state.phrase_delete_id = ""
                st.success("문구를 저장했습니다. 팀장/협력사 탭에서 이 문구를 골라 보내면 됩니다.")
                st.rerun()
    with s2:
        if edit_id and st.button("수정 취소", width="stretch"):
            st.session_state.phrase_edit_id = ""
            st.rerun()


def render_classify_tab(records: pd.DataFrame) -> None:
    st.caption("카톡·밴드 구인글 또는 사진을 넣으면 현장·프로젝트·협력사·연락처를 뽑습니다. 팀장/협력사로 나눠 저장됩니다.")
    st.text_area(
        "카톡 / 밴드 구인글",
        key="raw_text",
        height=150,
        placeholder="구인글을 통째로 붙여넣으세요.",
    )
    photos = st.file_uploader(
        "사진 (카톡·밴드 캡처, 명함 등)",
        type=["png", "jpg", "jpeg", "webp", "heic"],
        accept_multiple_files=True,
        key=f"photos_{st.session_state.upload_nonce}",
    )

    a1, a2 = st.columns(2)
    with a1:
        analyze = st.button("분석하기", type="primary")
    with a2:
        clear = st.button("입력 칸 비우기")

    if analyze:
        pending = list(photos or [])
        texts = [(st.session_state.raw_text or "").strip()]
        notes = []
        for file in pending:
            path = save_upload(file)
            st.session_state.image_paths = list(st.session_state.image_paths) + [str(path)]
            read = ocr_image(path).strip()
            if read:
                texts.append(read)
                notes.append("사진에서 글자를 읽었습니다.")
            else:
                notes.append("사진은 저장됨. 글자가 안 보이면 텍스트로도 붙여 주세요.")
        combined = "\n".join(t for t in texts if t)
        if combined:
            apply_parse(parse_source(combined))
            st.session_state.ocr_note = " ".join(notes) or "분석했습니다. 구분과 칸을 확인하세요."
        else:
            st.session_state.ocr_note = "분석할 문구 또는 사진이 없습니다."

    if clear:
        for key in [
            "raw_text", "field_site", "field_project", "field_company",
            "field_person", "field_phone", "field_email", "field_source",
        ]:
            st.session_state[key] = ""
        st.session_state.field_kind = "팀장"
        st.session_state.image_paths = []
        st.session_state.ocr_note = ""
        st.rerun()

    if st.session_state.ocr_note:
        st.caption(st.session_state.ocr_note)

    st.radio("이 건은 어디에 넣을까요?", options=["팀장", "협력사"], key="field_kind", horizontal=True)
    st.text_input("현장명", key="field_site")
    st.text_input("프로젝트", key="field_project")
    st.text_input("업체 (협력사명)", key="field_company")
    st.text_input("담당자", key="field_person")
    st.text_input("연락처", key="field_phone")
    st.text_input("이메일 (협력사 메일용)", key="field_email")

    cur = current_fields()
    has_contact = bool(digits_only(cur["연락처"]) or cur["이메일"])
    dup = find_duplicate(cur["연락처"], cur["이메일"], records) if has_contact else records.iloc[0:0]
    if st.session_state.save_msg:
        st.markdown(f"<div class='ok'>{st.session_state.save_msg}</div>", unsafe_allow_html=True)
    elif not has_contact:
        st.markdown("<div class='warn'>연락처 또는 이메일이 있어야 저장됩니다.</div>", unsafe_allow_html=True)
    elif not dup.empty:
        st.markdown("<div class='warn'>이미 같은 연락처/이메일이 저장되어 있습니다.</div>", unsafe_allow_html=True)

    if st.button("저장해서 해당 탭으로 보내기", disabled=(not has_contact) or (not dup.empty)):
        latest = load_records()
        if not find_duplicate(cur["연락처"], cur["이메일"], latest).empty:
            st.session_state.save_msg = "저장 직전에 중복이 확인되어 넣지 않았습니다."
        else:
            row = {
                "id": uuid.uuid4().hex[:12],
                "등록일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "카톡발송": "",
                "메일발송": "",
                **cur,
            }
            save_records(pd.concat([latest, pd.DataFrame([row])], ignore_index=True))
            st.session_state.selected_id = row["id"]
            st.session_state.save_msg = f"저장했습니다. 위 「{cur['구분']}」 탭에서 볼 수 있습니다."
            st.session_state.reset_form = True
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="하이테크잡스", page_icon="🏭", layout="centered", initial_sidebar_state="collapsed")
    inject_pwa()
    inject_css()
    init_state()
    persist.set_phrase_seed(default_phrases())
    if not require_login():
        return

    st.markdown('<p class="hero">하이테크잡스</p>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="sub">분류하기에 넣고, 팀장·협력사에서 고른 뒤 문구저장에서 만든 글로 보냅니다. 저장: {persist.storage_label()}</p>',
        unsafe_allow_html=True,
    )

    records = load_records()
    render_backup_bar(records)
    tab_in, tab_lead, tab_co, tab_phrase = st.tabs(["분류하기", "팀장", "협력사", "문구저장"])
    with tab_in:
        render_classify_tab(records)
    with tab_lead:
        render_excel_tab(records, "팀장")
    with tab_co:
        render_excel_tab(records, "협력사")
    with tab_phrase:
        render_phrase_tab()


if __name__ == "__main__":
    main()
