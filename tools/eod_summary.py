#!/usr/bin/env python3
import json, pathlib, re, sys
from datetime import datetime, timezone, timedelta, date

PATH_MD = pathlib.Path("habits/HABITS.md")
PATH_JSONL = pathlib.Path("habits/HABITS.jsonl")

def load_entries():
    entries=[]
    if PATH_JSONL.exists() and PATH_JSONL.stat().st_size>0:
        for i,line in enumerate(PATH_JSONL.read_text(encoding="utf-8").splitlines(), start=1):
            s=line.strip()
            if not s:
                continue
            try:
                obj=json.loads(s)
                if isinstance(obj, dict):
                    entries.append(obj)
            except Exception as e:
                print(f"WARNING: skipping invalid JSON at line {i}: {e}", file=sys.stderr)
    return entries

def parse_time(s):
    if not s: return None
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z","+00:00"))
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def within(d, start, end):
    return start <= d < end

def count(entries, start, end):
    ap=0; gh=0
    patterns={}
    for e in entries:
        ts=parse_time(e.get("time"))
        if not ts:
            continue
        if not within(ts, start, end):
            continue
        cat=(e.get("category") or "").lower()
        if cat=="anti-pattern": ap+=1
        elif cat=="good-habit": gh+=1
        pat=e.get("pattern") or e.get("pattern_name") or "unknown"
        patterns[pat]=patterns.get(pat,0)+1
    return ap, gh, patterns

def fmt_patterns(pats, n=5):
    items=sorted(pats.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
    return "\n".join(f"- {k} — {v}" for k,v in items) if items else "- (no data)"

def replace_log_index(md_text, total_entries, anti_open, good_total, iso_now):
    if "## Log Index" not in md_text:
        md_text = "# HABITS — Workflow Log\n\n## Log Index\n- Last update: _none yet_\n- Total entries: 0\n- Anti-patterns (open): 0\n- Good habits recorded: 0\n\n---\n\n" + md_text
    pattern = r"(## Log Index.*?)(?:\n- Last update:.*\n- Total entries:.*\n- Anti-patterns \(open\):.*\n- Good habits recorded:.*)"
    repl = f"\\1\n- Last update: {iso_now}\n- Total entries: {total_entries}\n- Anti-patterns (open): {anti_open}\n- Good habits recorded: {good_total}"
    if re.search(pattern, md_text, flags=re.S):
        md_text = re.sub(pattern, repl, md_text, flags=re.S)
    else:
        md_text = re.sub(r"(## Log Index[^\n]*\n)", f"\\1- Last update: {iso_now}\n- Total entries: {total_entries}\n- Anti-patterns (open): {anti_open}\n- Good habits recorded: {good_total}\n", md_text, flags=re.S)
    return md_text

def iso_start_of_week(d):  # Monday as start
    return d - timedelta(days=d.weekday())

def main():
    # Ensure HABITS.md exists
    if not PATH_MD.exists():
        PATH_MD.parent.mkdir(parents=True, exist_ok=True)
        PATH_MD.write_text("# HABITS — Workflow Log\n\n## Log Index\n- Last update: _none yet_\n- Total entries: 0\n- Anti-patterns (open): 0\n- Good habits recorded: 0\n\n---\n\n## Recent Entries\n\n---\n\n## Trend Notes\n- Last 7 days: _n/a_\n- Last 30 days: _n/a_\n- Notes: _n/a_\n", encoding="utf-8")

    entries = load_entries()
    now = datetime.now(timezone.utc)
    today = date.fromtimestamp(now.timestamp())
    start_today = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    start_tomorrow = start_today + timedelta(days=1)
    start_yesterday = start_today - timedelta(days=1)

    # Week windows (ISO week Mon..Sun)
    start_wtd = datetime.combine(iso_start_of_week(today), datetime.min.time(), tzinfo=timezone.utc)
    start_prev_week = start_wtd - timedelta(days=7)
    end_prev_week = start_wtd

    # Month windows
    start_mtd = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
    prev_month = (today.replace(day=1) - timedelta(days=1))
    start_prev_month = datetime(prev_month.year, prev_month.month, 1, tzinfo=timezone.utc)
    end_prev_month = start_mtd

    # Year windows
    start_ytd = datetime(today.year, 1, 1, tzinfo=timezone.utc)
    start_prev_year = datetime(today.year-1, 1, 1, tzinfo=timezone.utc)
    end_prev_year = start_ytd

    # Counts
    ap_today, gh_today, pat_today = count(entries, start_today, start_tomorrow)
    ap_yest, gh_yest, _ = count(entries, start_yesterday, start_today)

    ap_wtd, gh_wtd, pat_wtd = count(entries, start_wtd, start_tomorrow)
    ap_prev_wk, gh_prev_wk, _ = count(entries, start_prev_week, end_prev_week)

    ap_mtd, gh_mtd, pat_mtd = count(entries, start_mtd, start_tomorrow)
    ap_prev_m, gh_prev_m, _ = count(entries, start_prev_month, end_prev_month)

    ap_ytd, gh_ytd, pat_ytd = count(entries, start_ytd, start_tomorrow)
    ap_prev_y, gh_prev_y, _ = count(entries, start_prev_year, end_prev_year)

    # Totals for Log Index
    total = len([1 for e in entries if isinstance(e, dict)])
    good_total = sum(1 for e in entries if (e.get("category") or "").lower()=="good-habit")
    anti_open = 0
    for e in entries:
        if (e.get("category") or "").lower()=="anti-pattern":
            status=(e.get("status") or "").lower()
            if status not in ("mitigated","dismissed"):
                anti_open+=1

    iso_now = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    md = PATH_MD.read_text(encoding="utf-8")
    md = replace_log_index(md, total, anti_open, good_total, iso_now)

    def delta_str(curr, prev):
        d = curr - prev
        s = f"{curr} ({'+' if d>0 else ''}{d})"
        return s

    block = f"""
### EOD Summary — {iso_now}

**Today vs Yesterday**
- Anti-patterns: {delta_str(ap_today, ap_yest)}
- Good habits: {delta_str(gh_today, gh_yest)}
- Top patterns today:
{fmt_patterns(pat_today)}

**Week-to-Date vs Prior Week**
- Anti-patterns: {delta_str(ap_wtd, ap_prev_wk)}
- Good habits: {delta_str(gh_wtd, gh_prev_wk)}
- Frequent patterns (WTD):
{fmt_patterns(pat_wtd)}

**Month-to-Date vs Prior Month**
- Anti-patterns: {delta_str(ap_mtd, ap_prev_m)}
- Good habits: {delta_str(gh_mtd, gh_prev_m)}
- Frequent patterns (MTD):
{fmt_patterns(pat_mtd)}

**Year-to-Date vs Prior Year**
- Anti-patterns: {delta_str(ap_ytd, ap_prev_y)}
- Good habits: {delta_str(gh_ytd, gh_prev_y)}
- Frequent patterns (YTD):
{fmt_patterns(pat_ytd)}

_Generated by /eod manual script._
""".strip()

    # Ensure "## Auto Summaries" exists before appending EOD block
    if "## Auto Summaries" not in md:
        md += "\n\n## Auto Summaries\n"

    md += "\n\n" + block + "\n"
    PATH_MD.write_text(md, encoding="utf-8")
    print("EOD Summary appended to habits/HABITS.md")

if __name__=="__main__":
    main()
