import json
import argparse
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import gspread
from google.oauth2.service_account import Credentials

DB_PATH = Path("leet_srs.json")
CONFIG_PATH = Path("leet_config.json")

# ---------- Config Loader ----------
def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        sheet_id = cfg.get("sheet_id")
        sa_path = cfg.get("service_account")
        if sheet_id and sa_path:
            return sheet_id, sa_path
    return None, None

# ---------- Utility ----------
def today() -> date:
    return date.today()

def iso(d: Optional[date]) -> Optional[str]:
    return None if d is None else d.isoformat()

def parse_iso(s: Optional[str]) -> Optional[date]:
    return None if s is None else datetime.fromisoformat(s).date()

# ---------- Google Sheets helper ----------
def gs_client_from_service_account(sa_json_path: str):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(sa_json_path, scopes=scopes)
    return gspread.authorize(creds)

def sheet_to_list_of_dicts(worksheet) -> List[Dict[str,str]]:
    return worksheet.get_all_records()

def list_of_dicts_to_sheet(worksheet, rows: List[Dict[str, Any]]):
    headers = ["id","difficulty","ef","reps","interval","last_review","next_review","notes"]
    worksheet.clear()
    if not rows:
        worksheet.update([headers])
        return
    table = [headers]
    for r in rows:
        table.append([str(r.get(h,"")) for h in headers])
    worksheet.update(table)

# ---------- Spaced Repetition Core Logic ----------
class SRS:
    def __init__(self):
        self.sheet_id, self.sa_json_path = load_config()
        self.db = {"problems": {}}
        self.client = None
        if self.sheet_id and self.sa_json_path:
            try:
                self.client = gs_client_from_service_account(self.sa_json_path)
                self._load_from_sheet()
                print(f"Using Google Sheet: {self.sheet_id}")
            except Exception as e:
                print(f"Could not connect to Google Sheet, falling back to local JSON: {e}")
                self._load_local()
        else:
            self._load_local()

    def _load_local(self):
        if DB_PATH.exists():
            self.db = json.loads(DB_PATH.read_text())
        else:
            self.db = {"problems": {}}

    def _save_local(self):
        DB_PATH.write_text(json.dumps(self.db, indent=2, default=str))

    def _get_worksheet(self):
        sh = self.client.open_by_key(self.sheet_id)
        try:
            ws = sh.worksheet("problems")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="problems", rows="1000", cols="20")
        return ws

    def _load_from_sheet(self):
        ws = self._get_worksheet()
        rows = sheet_to_list_of_dicts(ws)
        problems = {}
        for r in rows:
            pid = str(r.get("id") or "").strip()
            if not pid:
                continue
            problems[pid] = {
                "id": pid,
                "difficulty": int(r.get("difficulty", 3)),
                "ef": float(r.get("ef", 2.5)),
                "reps": int(r.get("reps", 0)),
                "interval": int(r.get("interval", 3)),
                "last_review": r.get("last_review"),
                "next_review": r.get("next_review") or iso(today() + timedelta(days=3)),
                "notes": r.get("notes", "")
            }
        self.db = {"problems": problems}

    def _save_to_sheet(self):
        ws = self._get_worksheet()
        rows = list(self.db["problems"].values())
        list_of_dicts_to_sheet(ws, rows)

    # ---------- Core SRS Logic ----------
    def _make_entry(self, pid, diff):
        ef = max(1.3, 2.5 - 0.05 * (diff - 3))
        return {
            "id": pid, "difficulty": diff, "ef": ef,
            "reps": 0, "interval": 3,
            "last_review": None,
            "next_review": iso(today() + timedelta(days=3)),
            "notes": ""
        }

    def add_solved(self, pid, diff, notes=""):
        probs = self.db["problems"]
        if pid in probs:
            e = probs[pid]
            e.update({
                "difficulty": diff,
                "notes": notes or e.get("notes", ""),
                "ef": round(max(1.3, e.get("ef", 2.5) - 0.02 * (diff - 3)), 3),
                "reps": 0,
                "interval": 3,
                "next_review": iso(today() + timedelta(days=3))
            })
            print(f"Updated {pid}: next review in 3 days on {e['next_review']}")
        else:
            e = self._make_entry(pid, diff)
            e["notes"] = notes
            probs[pid] = e
            print(f"Added {pid} (difficulty {diff}). First review in 3 days on {e['next_review']}")
        self._persist()

    def record_review(self, pid, q):
        if pid not in self.db["problems"]:
            raise KeyError(f"{pid} not found")
        if not (0 <= q <= 5):
            raise ValueError("quality must be 0-5")
        e = self.db["problems"][pid]
        ef, reps, prev_i = e.get("ef", 2.5), e.get("reps", 0), e.get("interval", 3)
        if q < 3:
            reps, interval = 0, 3
        else:
            reps += 1
            interval = 10 if reps == 1 else max(1, round(prev_i * ef))
        ef_new = max(1.3, ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
        e.update({
            "ef": round(ef_new, 3),
            "reps": reps,
            "interval": interval,
            "last_review": iso(today()),
            "next_review": iso(today() + timedelta(days=interval))
        })
        self.db["problems"][pid] = e
        self._persist()
        print(f"{pid}: q={q}, next={e['next_review']} (in {interval}d, ef={e['ef']})")

    def _persist(self):
        if self.client:
            self._save_to_sheet()
        else:
            self._save_local()

    def get_due(self):
        d = today()
        due = [p for p in self.db["problems"].values() if not p.get("next_review") or parse_iso(p["next_review"]) <= d]
        due.sort(key=lambda x: (parse_iso(x["next_review"]) or today(), -x["difficulty"]))
        return due

    def study_plan_summary(self):
        d0, d1, d7, d30 = today(), today()+timedelta(1), today()+timedelta(7), today()+timedelta(30)
        counts = {"overdue":0,"due_today":0,"due_tomorrow":0,"next_7_days":0,"next_30_days":0,"total":0}
        for p in self.db["problems"].values():
            counts["total"]+=1
            nr=parse_iso(p.get("next_review"))
            if not nr:
                counts["due_today"]+=1; continue
            if nr<d0: counts["overdue"]+=1; counts["due_today"]+=1
            elif nr==d0: counts["due_today"]+=1
            elif nr==d1: counts["due_tomorrow"]+=1
            elif d1<nr<=d7: counts["next_7_days"]+=1
            elif d7<nr<=d30: counts["next_30_days"]+=1
        return counts

    def summary(self):
        plan=self.study_plan_summary()
        print(f"Total tracked: {plan['total']}")
        print(f"Due today: {plan['due_today']} (Overdue: {plan['overdue']})")
        print(f"Tomorrow: {plan['due_tomorrow']} | 2-7d: {plan['next_7_days']} | 8-30d: {plan['next_30_days']}")
        for p in sorted(self.db["problems"].values(), key=lambda x: parse_iso(x["next_review"]) or today()):
            print(f"{p['id']:12} | diff={p['difficulty']} ef={p['ef']:.2f} reps={p['reps']} interval={p['interval']}d next={p['next_review']}")

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("add");a.add_argument("pid");a.add_argument("diff",type=int);a.add_argument("notes",nargs="?",default="")
    r=sub.add_parser("review");r.add_argument("pid");r.add_argument("quality",type=int)
    sub.add_parser("due");sub.add_parser("summary");sub.add_parser("plan")
    args=parser.parse_args()
    s=SRS()
    if args.cmd=="add":s.add_solved(args.pid,args.diff,args.notes)
    elif args.cmd=="review":s.record_review(args.pid,args.quality)
    elif args.cmd=="due":
        due=s.get_due()
        print("Due problems:" if due else "Woohoo nothing due today!")
        for p in due:print(f"{p['id']:10} | diff={p['difficulty']} next={p['next_review']}")
    elif args.cmd=="summary":s.summary()
    elif args.cmd=="plan":
        p=s.study_plan_summary()
        print("Study plan summary")
        for k,v in p.items():print(f"{k:>15}: {v}")

if __name__=="__main__":
    main()
