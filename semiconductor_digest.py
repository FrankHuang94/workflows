#!/usr/bin/env python3
"""Daily semiconductor industry news digest using Google News RSS."""

from __future__ import annotations

import argparse
import os
import smtplib
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Iterable
from urllib.parse import quote_plus
from urllib.request import urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


PST_TZ = ZoneInfo("America/Los_Angeles")
GOOGLE_NEWS_SEARCH = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
SEMICONDUCTOR_TERMS = ["semiconductor", "chip industry", "integrated circuits", "foundry"]
SEMICONDUCTOR_COMPANIES = [
    "NVIDIA",
    "TSMC",
    "Intel",
    "Samsung Electronics",
    "AMD",
    "Qualcomm",
    "Broadcom",
    "Micron",
    "Texas Instruments",
    "SK hynix",
    "ASML",
    "Applied Materials",
    "Lam Research",
    "KLA",
    "MediaTek",
]
TOPIC_QUERIES = {
    "Strategy": ["strategy", "expansion", "roadmap", "partnership"],
    "Finance": ["finance", "revenue", "profit", "guidance"],
    "Earnings": ["earnings", "quarterly results", "EPS", "outlook"],
    "Investment": ["investment", "investments", "invesmtnet"],
    "Fundraising": ["fundraising", "funding round", "capital raise", "series"],
    "New Product Release": ["new product", "launch", "release", "porduct"],
    "Major Events": ["major event", "acquisition", "merger", "regulation", "sanctions"],
}
RFC822 = "%a, %d %b %Y %H:%M:%S %Z"


@dataclass
class Article:
    title: str
    link: str
    source: str
    published: datetime
    topic: str


class SemiconductorDigest:
    def __init__(self, lookback_hours: int = 24, max_articles: int = 60) -> None:
        self.lookback_hours = lookback_hours
        self.max_articles = max_articles

    def _query_strings(self) -> Iterable[tuple[str, str]]:
        for topic, keywords in TOPIC_QUERIES.items():
            for keyword in keywords:
                if topic == "Earnings":
                    for company in SEMICONDUCTOR_COMPANIES:
                        yield topic, f'("{company}") {keyword} semiconductor when:1d'
                    continue

                for sector in SEMICONDUCTOR_TERMS:
                    yield topic, f'("{sector}") {keyword} when:1d'

    def fetch_articles(self) -> list[Article]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        dedupe: set[str] = set()
        articles: list[Article] = []

        for topic, query in self._query_strings():
            url = GOOGLE_NEWS_SEARCH.format(query=quote_plus(query))
            xml_data = self._fetch_xml(url)
            if not xml_data:
                continue

            try:
                root = ET.fromstring(xml_data)
            except ET.ParseError:
                continue

            for item in root.findall("./channel/item"):
                link = self._text(item, "link")
                if not link or link in dedupe:
                    continue

                published = self._parse_published(self._text(item, "pubDate"))
                if not published or published < cutoff:
                    continue

                dedupe.add(link)
                source_el = item.find("source")
                source = source_el.text.strip() if source_el is not None and source_el.text else "Unknown"
                articles.append(
                    Article(
                        title=self._text(item, "title") or "(no title)",
                        link=link,
                        source=source,
                        published=published,
                        topic=topic,
                    )
                )

        articles.sort(key=lambda a: a.published, reverse=True)
        return articles[: self.max_articles]

    @staticmethod
    def _fetch_xml(url: str) -> str:
        try:
            with urlopen(url, timeout=20) as response:
                return response.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""

    @staticmethod
    def _parse_published(pub_date: str) -> datetime | None:
        if not pub_date:
            return None
        try:
            return datetime.strptime(pub_date, RFC822).astimezone(timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _text(parent: ET.Element, tag: str) -> str:
        element = parent.find(tag)
        return element.text.strip() if element is not None and element.text else ""

    def build_summary(self, articles: list[Article]) -> str:
        generated_at = datetime.now(PST_TZ).strftime("%Y-%m-%d %H:%M %Z")
        if not articles:
            return f"Semiconductor Daily Digest ({generated_at})\n\nNo qualifying articles found in the last 24 hours."

        by_topic: dict[str, list[Article]] = defaultdict(list)
        for article in articles:
            by_topic[article.topic].append(article)

        lines = [
            f"Semiconductor Daily Digest ({generated_at})",
            f"Collected {len(articles)} article(s) from the last {self.lookback_hours} hours.",
            "",
            "Topline by category:",
        ]

        for topic in TOPIC_QUERIES:
            lines.append(f"- {topic}: {len(by_topic.get(topic, []))} article(s)")

        earnings_articles = by_topic.get("Earnings", [])
        if earnings_articles:
            lines.append("\nEarnings spotlight (semiconductor companies):")
            for art in earnings_articles[:10]:
                pub = art.published.astimezone(PST_TZ).strftime("%Y-%m-%d %H:%M %Z")
                lines.append(f"• {art.title}")
                lines.append(f"  Source: {art.source} | Published: {pub}")
                lines.append(f"  Link: {art.link}")

        lines.append("\nDetailed highlights:")
        for topic in TOPIC_QUERIES:
            topic_articles = by_topic.get(topic, [])[:8]
            if not topic_articles:
                continue
            lines.extend([f"\n{topic}", "-" * len(topic)])
            for art in topic_articles:
                pub = art.published.astimezone(PST_TZ).strftime("%Y-%m-%d %H:%M %Z")
                lines.extend(
                    [
                        f"• {art.title}",
                        f"  Source: {art.source} | Published: {pub}",
                        f"  Link: {art.link}",
                    ]
                )

        return "\n".join(lines)


def send_email(subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("EMAIL_SENDER", smtp_user or "")
    recipient = os.getenv("EMAIL_RECIPIENT")

    required = {
        "SMTP_HOST": smtp_host,
        "SMTP_USER": smtp_user,
        "SMTP_PASSWORD": smtp_password,
        "EMAIL_RECIPIENT": recipient,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)


def run_digest(max_articles: int, dry_run: bool = False) -> None:
    digest = SemiconductorDigest(max_articles=max_articles)
    articles = digest.fetch_articles()
    summary = digest.build_summary(articles)
    subject = f"Semiconductor Daily Digest - {datetime.now(PST_TZ).strftime('%Y-%m-%d')}"

    if dry_run:
        print(summary)
        return

    send_email(subject, summary)
    print(f"Sent summary email with {len(articles)} article(s).")


def next_run_time(now: datetime | None = None) -> datetime:
    now = now or datetime.now(PST_TZ)
    run = now.replace(hour=8, minute=0, second=0, microsecond=0)
    return run if now < run else run + timedelta(days=1)


def run_scheduler(max_articles: int, dry_run: bool = False) -> None:
    print("Scheduler started. Daily digest will run at 8:00 AM America/Los_Angeles.")
    while True:
        now = datetime.now(PST_TZ)
        run_at = next_run_time(now)
        sleep_seconds = max(1, int((run_at - now).total_seconds()))
        print(f"Next run at {run_at.isoformat()} ({sleep_seconds}s from now).")
        time.sleep(sleep_seconds)
        run_digest(max_articles, dry_run=dry_run)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send daily semiconductor news summary email.")
    parser.add_argument("--run-once", action="store_true", help="Run immediately and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print summary without sending email.")
    parser.add_argument("--max-articles", type=int, default=60, help="Cap total articles in the digest.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.run_once:
        run_digest(args.max_articles, dry_run=args.dry_run)
    else:
        run_scheduler(args.max_articles, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
