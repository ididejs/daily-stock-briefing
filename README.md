# 📊 Daily Stock Briefing (GitHub Actions)

매일 **KST 오전 8시 30분**에 국내외 증시 주요 뉴스·매크로 지표·개장 전 체크포인트를 자동 수집·요약하여 **이메일(HTML 본문 + `.md` 파일 첨부)**로 받아보는 GitHub Actions 프로젝트입니다.

---

## 1. 사전 준비

### ① Gemini API 키 발급
1. [Google AI Studio](https://aistudio.google.com/)에 로그인합니다.
2. **Get API key → Create API key**를 눌러 API 키를 발급받습니다.

### ② Gmail 앱 비밀번호 발급 (2단계 인증 필요)
1. Google 계정 관리 → **보안** → **2단계 인증**을 켭니다.
2. 보안 메뉴 또는 검색창에서 **앱 비밀번호(App passwords)**로 이동합니다.
3. 앱 이름(예: `GitHub Stock Briefing`)을 입력하고 생성된 **16자리 비밀번호**를 복사해 둡니다. (공백 제거 후 사용)

---

## 2. GitHub 저장소 설정

1. GitHub에서 새 저장소를 생성합니다. (**Private** 저장소 권장)
2. 이 폴더의 파일들을 해당 저장소에 업로드(push)합니다.
3. 저장소의 **Settings → Secrets and variables → Actions → New repository secret**에서 아래 4개의 Secret을 등록합니다.

| Secret 이름 | 설명 | 예시 |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio에서 발급한 API 키 | `AIzaSy...` |
| `EMAIL_SENDER` | 발신용 Gmail 주소 | `myname@gmail.com` |
| `EMAIL_PASSWORD` | Gmail 16자리 앱 비밀번호 | `abcdefghijklmnop` |
| `EMAIL_RECEIVER` | 수신할 이메일 주소 (본인 메일) | `myname@gmail.com` |

---

## 3. 테스트 실행 및 자동 스케줄

- **즉시 테스트**: GitHub 저장소 상단 **Actions** 탭 → **Daily Stock Briefing (08:30 KST)** → **Run workflow** 버튼을 누르면 즉시 실행되어 메일함으로 브리핑이 도착합니다.
- **자동 실행 시간**: 매일 **UTC 23:30 (= KST 오전 8:30)**에 자동 실행됩니다.
  - 평일(월~금)에만 받고 싶다면 `.github/workflows/daily-briefing.yml`의 cron을 `'30 23 * * 0-4'`로 변경하세요.
  - 생성된 마크다운 파일은 저장소 내 `reports/YYYY-MM-DD_증시뉴스요약.md`에도 자동 보관됩니다.
