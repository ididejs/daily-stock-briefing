import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import feedparser
import markdown
from google import genai
from google.genai import types

KST = timezone(timedelta(hours=9))

RSS_FEEDS = {
    "한국경제 증권": "https://www.hankyung.com/feed/finance",
    "매일경제 증권": "https://www.mk.co.kr/rss/50200011/",
    "연합뉴스 경제": "https://www.yna.co.kr/rss/economy.xml",
    "CNBC Markets": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
    "MarketWatch Top Stories": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}


def fetch_rss_headlines(limit_per_feed: int = 8) -> str:
    """Collect recent headlines from major financial news RSS feeds."""
    sections: list[str] = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            items = []
            for entry in feed.entries[:limit_per_feed]:
                title = getattr(entry, "title", "").strip()
                published = getattr(entry, "published", "").strip()
                if title:
                    items.append(f"- {title} ({published})" if published else f"- {title}")
            if items:
                sections.append(f"### {source}\n" + "\n".join(items))
        except Exception as exc:
            sections.append(f"### {source}\n- 수집 실패: {exc}")
    return "\n\n".join(sections)


def build_prompt(today_str: str, rss_context: str) -> str:
    """Build the structured prompt for the daily morning stock briefing."""
    return f"""오늘은 {today_str} (KST, 한국 표준시)입니다.
오전 9시 국내 증시 개장 전 모닝 브리핑을 위해 국내외 증시 주요 뉴스와 지표를 조사하여 마크다운(.md) 문서로 작성해 주세요.

[출처 원칙]
- 주요 경제지·통신사·공식 기관 발표만 참고하세요.
- 개인 의견이 들어간 유튜브·블로그·SNS 게시물은 절대 참고하지 마세요.
- 확인되지 않은 수치나 사실은 추측하지 말고, 확인 가능한 최신 수치와 기준 시점을 명확히 적으세요.

[분량 및 스타일]
- 표와 핵심 배경·수치·이슈 설명이 포함된 균형형 브리핑(읽는 시간 3~5분 분량)으로 작성하세요.

[문서 구성]
# 📊 국내외 증시 모닝 브리핑 ({today_str} KST)

## 💡 오늘의 3줄 핵심 요약
(가장 중요한 3가지 포인트를 번호 목록으로 정리)

## 1. 해외 증시 (직전 거래일 미국 시장 마감)
- 미국 주요 3대 지수(다우존스30, S&P 500, 나스닥 종합) 마감 지수 및 등락률 표
- 빅테크 및 전 섹터(반도체/AI, 2차전지, 바이오, 금융, 에너지/방산 등 균형) 핵심 이슈
- 연준(Fed) 금리·통화정책 및 주요 거시경제 지표 발표 요약

## 2. 글로벌 매크로 지표
- 미 국채 10년물·2년물 금리, 원/달러 환율, 국제유가(WTI·브렌트유), 국제 금, 비트코인 현황 표 및 변동 배경

## 3. 국내 증시 개장 전 체크포인트
- 전일 코스피/코스닥 마감 요약, 코스피200 야간선물 및 원/달러 환율 동향
- 오늘 오전 9시 개장 전 주목할 주요 공시·외국인/기관 수급 포인트·주도 테마
- 전 섹터 균형 주요 동향 (반도체, 2차전지, 바이오, 금융, 방산·조선 등)

## 4. 이번 주 / 오늘의 주요 일정 (KST 기준)
- 당일 및 이번 주 국내외 경제지표 발표, 기업 실적, 주요 증시 이벤트

## 5. 참고 출처
- 참고한 주요 언론사 및 공식 기관명 목록

---
참고용 최신 RSS 헤드라인:
{rss_context}
"""


def generate_briefing(today_str: str, rss_context: str) -> str:
    """Generate the markdown briefing using Gemini API with Google Search grounding."""
    api_key = os.environ["GEMINI_API_KEY"]
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=build_prompt(today_str, rss_context),
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini API returned an empty response.")
    return response.text.strip()


def save_report(today_str: str, content: str) -> Path:
    """Save the markdown report to reports/YYYY-MM-DD_증시뉴스요약.md."""
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{today_str}_증시뉴스요약.md"
    report_path.write_text(content + "\n", encoding="utf-8")
    return report_path


def send_email(today_str: str, md_content: str, report_path: Path) -> None:
    """Send the briefing as an HTML email with the .md file attached via Gmail SMTP."""
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    receiver = os.environ.get("EMAIL_RECEIVER", sender)

    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code"],
    )
    styled_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #222; max-width: 780px; margin: 0 auto; padding: 16px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 10px; text-align: left; }}
  th {{ background-color: #f6f8fa; }}
  blockquote {{ border-left: 4px solid #ccc; margin: 10px 0; padding-left: 12px; color: #555; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

    msg = EmailMessage()
    msg["Subject"] = f"[모닝 브리핑] {today_str} 국내외 증시 주요 뉴스 요약"
    msg["From"] = sender
    msg["To"] = receiver
    msg.set_content(md_content)
    msg.add_alternative(styled_html, subtype="html")

    msg.add_attachment(
        report_path.read_bytes(),
        maintype="text",
        subtype="markdown",
        filename=report_path.name,
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)


def main() -> None:
    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")

    rss_context = fetch_rss_headlines()
    briefing_md = generate_briefing(today_str, rss_context)
    report_path = save_report(today_str, briefing_md)
    send_email(today_str, briefing_md, report_path)
    print(f"Successfully generated and emailed {report_path}")


if __name__ == "__main__":
    main()
