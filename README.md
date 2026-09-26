# 하이테크잡스

받은 **문구·사진**을 분석해 현장명, 프로젝트, 협력사, 연락처를 저장합니다.

위쪽 탭: **분류하기 · 팀장 · 협력사 · 문구저장**

아이폰 사파리에서 홈 화면에 추가하면 앱처럼 쓸 수 있습니다.

---

## 쓰는 순서

1. **문구저장**에서 팀장 카톡 / 협력사 메일 문구를 만듭니다. `{현장명}` `{프로젝트}` `{협력사명}` `{담당자}` `{연락처}` `{이메일}` 을 넣으면 보낼 때 채워집니다.
2. **분류하기**에 카톡·밴드 구인글 또는 사진을 넣고 **분석하기**, 팀장/협력사로 저장합니다.
3. **팀장**에서 한 건을 고르고, 저장된 문구를 한눈에 본 뒤 카톡 문구를 복사합니다. 카톡은 명함을 자동으로 넣지 못하므로, 저장한 명함 사진을 직접 첨부합니다.
4. **협력사**에서 **보내는 메일 바꾸기**에 Gmail과 앱 비밀번호를 넣은 뒤, 한 건을 고르고 **메일 보내기**를 누릅니다. **내 명함**을 넣어 두면 메일에 같이 첨부됩니다.

핸드폰에서는 목록이 **카드**로 보입니다. 컴퓨터에서는 **표**가 기본입니다.

이미 보낸 협력사 메일은 다시 보낼 수 없습니다. 같은 이메일 주소로 한 번 나갔으면, 다른 건이어도 추가 발송되지 않습니다.

협력사 메일은 **보내는 Gmail**에서 나갑니다. Google 계정에서 2단계 인증을 켠 뒤 [앱 비밀번호](https://myaccount.google.com/apppasswords) 16자리를 만듭니다. 로그인 비밀번호는 쓸 수 없습니다.

---

## 1. 이 컴퓨터에서 실행

```powershell
cd "C:\Users\user\OneDrive\바탕 화면\hitech-job-app"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

브라우저: `http://localhost:8501`

같은 와이파이 아이폰은 터미널의 **Network URL** 을 Safari에 넣습니다.

---

## 2. 핸드폰에서 언제든 쓰려면 (Streamlit Cloud)

클라우드에 올리면 `https://xxxx.streamlit.app` 주소로 폰에서 열 수 있습니다. 이 PC를 켜 두지 않아도 됩니다.

### 준비

1. [github.com](https://github.com) 에서 계정을 만들고, 빈 저장소 `hitech-job-app` 을 만듭니다. (Public이어도 됩니다. 연락처 파일은 올리지 않습니다.)
2. 이 PC 터미널에서 한 번만 이름과 이메일을 넣습니다.

```powershell
git config --global user.name "이름"
git config --global user.email "이메일@example.com"
```

3. 같은 폴더에서 코드를 올립니다.

```powershell
cd "C:\Users\user\OneDrive\바탕 화면\hitech-job-app"
git add app.py persist.py requirements.txt README.md .gitignore .streamlit/config.toml .streamlit/secrets.toml.example data/phrases.json static/icon.png
git commit -m "하이테크잡스 앱"
git remote add origin https://github.com/본인아이디/hitech-job-app.git
git push -u origin main
```

`secrets.toml`, `data/collected_jobs.csv`, `data/hitech_jobs.db` 는 올리지 마세요.

4. [share.streamlit.io](https://share.streamlit.io) 에서 GitHub로 로그인 → **Create app** → 방금 올린 저장소, 브랜치 `main`, 파일 `app.py`

### Secrets에 넣을 값

**App settings → Secrets**

```toml
app_password = "본인만-아는-비밀번호"
```

비밀번호를 넣지 않으면 주소를 아는 사람이 목록을 볼 수 있습니다.

### 목록이 사라지지 않게 (구글 시트)

Streamlit Cloud는 잠들었다가 켜지면 서버 안의 파일이 지워질 수 있습니다. 구글 시트를 연결하면 목록과 문구가 남습니다.

1. [Google Cloud Console](https://console.cloud.google.com/) 에서 프로젝트를 만들고 **Google Sheets API**, **Google Drive API** 를 켭니다.
2. **서비스 계정**을 만들고 JSON 키를 받습니다.
3. 빈 구글 시트를 만들고, 서비스 계정 이메일(예: `...@....iam.gserviceaccount.com`)에 **편집자** 권한을 줍니다.
4. 시트 주소 `https://docs.google.com/spreadsheets/d/이부분/edit` 의 아이디를 복사합니다.
5. Secrets에 `.streamlit/secrets.toml.example` 을 참고해 `sheets.spreadsheet_id` 와 `[gcp_service_account]` 전체를 넣습니다.

시트를 아직 안 넣었다면 앱 아래 **백업 / 복원**에서 CSV를 받아 두세요.

---

## 3. 아이폰 홈 화면에 추가

1. **Safari**로 앱 주소를 엽니다. (Chrome 공유는 잘 안 되는 경우가 많습니다.)
2. 아래 **공유** → **홈 화면에 추가**
3. 이름은 `하이테크잡스`

---

## 파일

- `app.py` — 화면
- `persist.py` — 로컬 파일 / 구글 시트 저장
- `requirements.txt` — 설치 목록
- `.streamlit/secrets.toml.example` — 비밀번호·시트 설정 보기
- `data/` — 이 컴퓨터에 저장된 목록 (GitHub에 올리지 않음)
