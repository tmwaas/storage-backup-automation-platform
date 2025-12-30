from prometheus_client import start_http_server, Gauge
import requests, time, datetime

API_BASE="http://localhost:5000/api/v1"
RPO_HOURS=24

vol_count = Gauge("storage_volume_count", "Number of volumes")
backup_last_ts = Gauge("backup_last_success_timestamp", "Unix timestamp of last backup", ["volume"])
backup_rpo_violation = Gauge("backup_rpo_violation", "1 if RPO violated else 0", ["volume"])

def parse_iso(ts: str) -> float:
    ts = ts.replace("Z","")
    dt = datetime.datetime.fromisoformat(ts)
    return dt.replace(tzinfo=datetime.timezone.utc).timestamp()

def scrape_loop():
    start_http_server(9100)
    while True:
        try:
            vols = requests.get(f"{API_BASE}/volumes", timeout=2).json().get("volumes", [])
            backups = requests.get(f"{API_BASE}/backups", timeout=2).json().get("backups", [])

            vol_count.set(len(vols))

            now = time.time()
            rpo_seconds = RPO_HOURS * 3600

            for v in vols:
                vname = v["name"]
                v_backups = [b for b in backups if b.get("volume_name") == vname]
                if not v_backups:
                    backup_last_ts.labels(volume=vname).set(0)
                    backup_rpo_violation.labels(volume=vname).set(1)
                    continue

                latest = sorted(v_backups, key=lambda x: x["created_at"])[-1]
                last = parse_iso(latest["created_at"])
                backup_last_ts.labels(volume=vname).set(last)
                violation = 1 if (now - last) > rpo_seconds else 0
                backup_rpo_violation.labels(volume=vname).set(violation)

        except Exception as e:
            print("Scrape error:", e)

        time.sleep(10)

if __name__ == "__main__":
    scrape_loop()
