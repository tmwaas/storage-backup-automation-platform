# Simple client to trigger backups and fetch results
import requests, time, json

API='http://localhost:5000/api/v1'

def trigger_backup(volume):
    r = requests.post(f'{API}/backup', json={'volume': volume})
    return r.json()

if __name__ == '__main__':
    vols = requests.get(f'{API}/volumes').json().get('volumes', [])
    for v in vols:
        res = trigger_backup(v['name'])
        print('Backup:', res)
