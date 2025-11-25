# Notifier (Slack webhook placeholder)
import requests, os

SLACK_WEBHOOK = os.environ.get('SLACK_WEBHOOK', 'https://hooks.slack.com/services/XXX/YYY/ZZZ')

def send_slack(msg):
    payload = {'text': msg}
    try:
        requests.post(SLACK_WEBHOOK, json=payload, timeout=5)
    except Exception as e:
        print('Failed to send slack message', e)

if __name__ == '__main__':
    send_slack('Test message from infra automation project')
