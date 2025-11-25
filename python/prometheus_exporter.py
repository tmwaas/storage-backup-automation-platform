# Prometheus exporter: scrapes mock storage API and exposes metrics
from prometheus_client import start_http_server, Gauge
import requests, time

API='http://localhost:5000'
vol_count = Gauge('storage_volume_count', 'Number of volumes')
last_backup_status = Gauge('backup_status', 'Last backup status (1=pass,0=fail)', ['volume'])
last_backup_ts = Gauge('backup_last_timestamp', 'Timestamp of last backup', ['volume'])

def scrape_loop():
    start_http_server(9100)
    while True:
        try:
            vols = requests.get(f'{API}/volumes').json().get('volumes', [])
            vol_count.set(len(vols))
            backups = requests.get(f'{API}/backup').json() if False else None
            # we don't have a backup listing endpoint in the mock, so we skip detailed scraping
        except Exception as e:
            print('Scrape error', e)
        time.sleep(10)

if __name__ == '__main__':
    scrape_loop()
