import os
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import feedparser
import markdown
import yfinance as yf
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

MARKET_TICKERS = {
    "다우존스30": "^DJI",
    "S&P 500": "^GSPC",
    "나스닥 종합": "^IXIC",
    "코스피 (KOSPI)": "^KS11",
    "코스닥 (KOSDAQ)": "^KQ11",
    "원/달러 환율": "KRW=X",
    "미 국채 10년물 금리(%)": "^TNX",
    "WTI 유가 (달러)": "CL=F",
    "브렌트유 (달러)": "BZ=F",
    "국제 금 (달러)": "GC=F",
    "비트코인 (USD)": "BTC-USD",
}


def strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    clean = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", clean).strip()


def fetch_market_snapshot() -> str:
    """Fetch latest closing price and daily change for key indices and macro indicators."""
    lines: list[str] = []
    for name, symbol in MARKET_TICKERS.items():
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                last_close = float(hist["Close"].iloc[-1])
                pct = ((last_close - prev_close) / prev_close) * 100
                date_str = hist.index[-1].strftime("%Y-%m-%d")
                lines.append(
                    f"- {name} ({symbol}): {last_close:,.2f} (전일 대비 {pct:+.2f}%, 기준일 {date_str})"
                )
            elif len(hist) == 1:
                last_close = float(hist["Close"].iloc[-1])
                date_str = hist.index[-1].strftime("%Y-%m-%d")
                lines.append(f"- {name} ({symbol}): {last_close:,.2f} (기준일 {date_str})")
        except Exception as exc:
            lines.append(f"- {name} ({symbol}): 조회 실패 ({exc})")
    return "\n".join(lines)


def fetch_rss_headlines(limit_per_feed: int = 12) -> str:
    """Collect recent headlines and summaries from major financial news RSS feeds."""
    sections: list[str] = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            items = []
            for entry in feed.entries[:limit_per_feed]:
                title = getattr(entry, "title", "").strip()
                summary = strip_html(getattr(entry, "summary", ""))[:220]
                published = getattr(entry, "published", "").strip()
                if title:
                    line = f"- **{title}**"
                    if published:
                        line += f" ({published})"
                    if summary:
                        line += f" — {summary}"
                    items.append(line)
            if items:
                sections.append(f"### {source}\n" + "\n".join(items))
        except Exception as exc:
            sections.append(f"### {source}\n- 수집 실패: {exc}")
    return "\n\n".join(sections)


def build_prompt(today_str: str, market_snapshot: str, rss_context: str) -> str:
    """Build the structured prompt for the daily morning stock briefing."""
    return f"""오늘은 {today_str} (KST, 한국 표준시)입니다.
오전 9시 국내 증시 개장 전 모닝 브리핑을 위해 아래 제공된 [실제 시장 지표 데이터]와 [주요 언론사 RSS 뉴스]를 바탕으로 마크다운(.md) 문서를 작성해 주세요.

[작성 원칙]
- 제공된 수치와 뉴스 내용에 기반해 정확히 작성하고, 확인되지 않은 수치나 일정은 절대 지어내지 마세요.
- 개인 의견이 들어간 유튜브·블로그·SNS 내용은 배제하고 주요 경제지·통신사 기사 위주로 정리하세요.
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
- 미 국채 10년물 금리, 원/달러 환율, 국제유가(WTI·브렌트유), 국제 금, 비트코인 현황 표 및 변동 배경

## 3. 국내 증시 개장 전 체크포인트
- 전일 코스피/코스닥 마감 요약 및 원/달러 환율 동향
- 오늘 오전 9시 개장 전 주목할 주요 기업·수급·정책·테마 뉴스
- 전 섹터 균형 주요 동향 (반도체, 2차전지, 바이오, 금융, 방산·조선 등)

## 4. 이번 주 / 오늘의 주요 일정 및 체크포인트
- 뉴스에서 언급된 주요 경제지표 발표, 통화정책 회의, 실적·증시 이벤트

## 5. 참고 출처
- Yahoo Finance 시장 데이터 및 참고한 주요 언론사 목록

---
[실제 시장 지표 데이터]
{market_snapshot}

---
[주요 언론사 최신 RSS 뉴스]
{rss_context}
"""


def generate_briefing(today_str: str, market_snapshot: str, rss_context: str) -> str:
    """Generate the markdown briefing using Gemini 4 Hydrogen."""
    api_key = os.environ["GEMINI_API_KEY"]
    model_name = os.environ.get("GEMINI_MODEL", "gemini-4-hydrogen")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=build_prompt(today_str, market_snapshot, rss_context),
        config=types.GenerateContentConfig(
            temperature=0.3,
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini API returned an empty response.")
    actual_model = getattr(response, "model_version", None) or model_name
    print(f"Generated briefing using model: {actual_model} (requested: {model_name})")
    footer = f"\n\n---\n*Generated by `{actual_model}` (requested: `{model_name}`)*"
    return response.text.strip() + footer


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

    market_snapshot = fetch_market_snapshot()
    rss_context = fetch_rss_headlines()
    briefing_md = generate_briefing(today_str, market_snapshot, rss_context)
    report_path = save_report(today_str, briefing_md)
    send_email(today_str, briefing_md, report_path)
    print(f"Successfully generated and emailed {report_path}")


if __name__ == "__main__":
    main()
