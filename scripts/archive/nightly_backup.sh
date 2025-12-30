#!/usr/bin/env bash

# This script is kept for Ansible-only execution scenarios
# (manual testing, CI pipelines, disaster recovery).
# Production scheduling is handled by backup-scheduler container.

set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
ansible-playbook ansible/playbooks/backup_trigger.yml
ansible-playbook ansible/playbooks/backup_validate.yml
