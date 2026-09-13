"""Download one Discord text channel for one Vietnam calendar day; no LLM calls."""

import argparse
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
VN = timezone(timedelta(hours=7))
DISCORD_EPOCH_MS = 1420070400000


def snowflake_boundary(moment):
    return str((int(moment.timestamp() * 1000) - DISCORD_EPOCH_MS) << 22)


def fetch_messages(session, channel_id, start, end, max_pages=20):
    """Return a bounded snapshot; never label truncated pagination as complete."""
    messages = {}
    before = snowflake_boundary(end)
    complete = False
    for _ in range(max_pages):
        response = session.get(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            params={"limit": 100, "before": before}, timeout=30,
        )
        if response.status_code != 200:
            hints = {
                401: "Invalid bot token.",
                403: "Check bot channel access and Read Message History permission.",
                404: "Channel not found or inaccessible.",
                429: "Rate limited; retry later using Discord Retry-After guidance.",
            }
            raise RuntimeError(f"Discord HTTP {response.status_code}. " + hints.get(response.status_code, "Try again later."))
        batch = response.json()
        if not batch:
            complete = True
            break
        for item in batch:
            sent = datetime.fromisoformat(item["timestamp"])
            if start <= sent < end:
                author = item.get("author", {})
                messages[item["id"]] = {
                    "id": item["id"],
                    "author_id": author.get("id"),
                    "author": author.get("global_name") or author.get("username"),
                    "timestamp": sent.astimezone(VN).isoformat(),
                    "content": item.get("content", ""),
                    "reply_to": (item.get("message_reference") or {}).get("message_id"),
                    "type": item.get("type"),
                    "attachment_count": len(item.get("attachments", [])),
                }
        if min(datetime.fromisoformat(item["timestamp"]) for item in batch) < start:
            complete = True
            break
        next_before = min(batch, key=lambda item: int(item["id"]))["id"]
        if int(next_before) >= int(before):
            raise RuntimeError("Pagination did not advance; no snapshot saved.")
        before = next_before
    return sorted(messages.values(), key=lambda item: int(item["id"])), complete


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default=os.getenv("DISCORD_CHANNEL_ID"))
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(VN).date())
    parser.add_argument("--max-pages", type=int, default=20)
    args = parser.parse_args()
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token or token.startswith("your_"):
        parser.error("Set DISCORD_BOT_TOKEN in .env (do not paste it in chat).")
    if not args.channel or not args.channel.isascii() or not args.channel.isdigit():
        parser.error("Set DISCORD_CHANNEL_ID in .env or pass --channel with a numeric ID.")
    if args.max_pages < 1:
        parser.error("--max-pages must be positive.")
    fetched_at = datetime.now(VN)
    start = datetime.combine(args.date, time.min, tzinfo=VN)
    if start > fetched_at:
        parser.error("Cannot fetch a future day.")
    end = min(start + timedelta(days=1), fetched_at)
    try:
        with requests.Session() as session:
            session.headers.update({"Authorization": f"Bot {token}"})
            messages, complete = fetch_messages(session, args.channel, start, end, args.max_pages)
    except requests.RequestException:
        parser.exit(1, "Network request failed; no snapshot saved. Check your connection.\n")
    except (RuntimeError, ValueError, KeyError, TypeError) as error:
        # Never print response bodies, headers, or credentials.
        message = str(error) if isinstance(error, RuntimeError) else "Unexpected Discord response."
        parser.exit(1, message + "\n")
    snapshot = {
        "channel_id": args.channel, "date": args.date.isoformat(),
        "timezone": "Asia/Ho_Chi_Minh", "fetched_at": fetched_at.isoformat(),
        "start_inclusive": start.isoformat(), "end_exclusive": end.isoformat(),
        "complete": complete, "message_count": len(messages), "messages": messages,
        "scope": "Direct channel messages only; no threads or attachment contents.",
    }
    folder = ROOT / "data" / "private"
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"discord_{args.channel}_{args.date}_{fetched_at.strftime('%H%M%S%f')}.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(messages)} messages. Pagination complete: {complete}. File: {output}")
    if not messages:
        print("No messages returned: verify Read Message History before assuming the day is empty.")
    elif not any(item["content"] for item in messages):
        print("All text content is empty: check Message Content Intent; attachments are not read.")
    if not complete:
        print("Page limit reached. This snapshot does not cover the entire requested interval.")
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
