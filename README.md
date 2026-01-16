# Infrastructure Automation – Storage & Backup Platform 

## Overview

This repository provides a **production-style simulation** of an automated **storage and backup platform**, designed to reflect real-world enterprise and telco-grade operational patterns.

Although implemented as a simulation lab, the architecture, automation flows, monitoring, alerting, and orchestration mechanisms closely mirror what is commonly found in **large-scale enterprise IT and telecom environments**, including the use of **Ansible AWX** for centralized automation control.

The project demonstrates how **API-driven storage services**, **scheduled backups**, **observability**, and **infrastructure automation** can be designed, operated, and monitored in a consistent, scalable, and auditable manner.

---

## Key Capabilities

### ✅ API-Driven Storage Service
A Python (Flask)–based REST API that supports:

- Create and delete storage volumes  
- Trigger backups per volume or for all volumes  
- List backups and volumes  
- Expose Prometheus-compatible metrics (`/metrics`)  
- Provide health checks (`/health`)  

### ✅ Persistent Storage Backend (MinIO – S3 Compatible)
MinIO is used to simulate an object-storage backend:

- Volume metadata stored in a dedicated bucket  
- Backup artifacts stored in a backup bucket  
- Fully API-driven access, similar to AWS S3 or enterprise object storage 

![MinIO Storage Dashboard](MinIO-Dashboard.jpg) 

### ✅ Automated Backup Scheduling
A dedicated **backup scheduler container** executes automatic backups using **cron**:

- Daily scheduled backups for all volumes  
- Centralized logging of backup execution  
- API-driven backup triggers (no direct storage coupling)  
- Designed to mimic enterprise backup orchestration services  

The scheduler is **health-aware** and only executes backup jobs once the Storage API is fully available and responding.

### ✅ Service Health Checks & Dependency Management
To improve reliability and prevent race conditions during startup, the platform implements container-level health checks and service dependencies.

Key aspects:

- The Storage API exposes a `/health` endpoint used to indicate readiness.
- Docker Compose health checks validate API availability before dependent services start.
- The Backup Scheduler container waits until the Storage API is marked as **healthy** before executing scheduled backups.
- This prevents missed or failed backup jobs caused by unavailable APIs during container startup or restarts.

This design reflects real-world production patterns where backup orchestration services must depend on application readiness rather than container start order alone.

### ✅ Infrastructure & Operational Automation (Ansible + AWX)
The project supports **two automation execution models**:

#### CLI-Based Ansible Automation
Used for local and ad-hoc execution of operational workflows such as:

- Storage provisioning
- Manual backup triggering
- Backup validation
- Cleanup automation
- Lifecycle Management (LCM) upgrade simulation
- Post-upgrade health checks

#### Centralized Automation with Ansible AWX
AWX is used to provide:

- Centralized job execution and visibility  
- Role-based access to automation workflows  
- Job scheduling and audit trails  
- Workflow orchestration across multiple playbooks  

Implemented Job Templates in AWX include:

- 01 – Provision Volume  
- 02 – Trigger Backup  
- 03 – Validate Backups  
- 04 – Upgrade Simulation (LCM)  
- 05 – Health Check  

A **Workflow Job Template** orchestrates the full lifecycle:

**End-to-End Storage Lifecycle**
```
Provision → Backup → Validation → Health Check
```

This setup closely reflects how enterprise teams use **Ansible Tower / AWX** in production environments.

![AWX Dashboard Overview](AWX-Dashboard-new.jpg)

![AWX Templates](AWX-Templates.jpg)

### ✅ Observability & Monitoring (Prometheus + Grafana)
The platform exposes custom metrics and provides full observability:

**Prometheus Metrics**
- `storage_volume_count`  
- `backup_operations_total`  
- `backup_failures_total`  
- `backup_last_success_timestamp`  
- `backup_rpo_violation`  

![Prometheus Status Target](prometheus-targets-updated.jpg)

**Grafana Dashboard**
- RPO violations per volume  
- Last successful backup timestamp per volume  
- Backup operation rate (5-minute window)  
- Total backup operations  
- Total storage volumes  
- Backup failures overview 

![Grafana Dashboard Overview](grafana-dashboard-storage-backup-automation-health.jpg)

All dashboards are built using **real PromQL queries** and production-style visualization patterns.

### ✅ Alerting
Alert rules are defined for operational visibility, including:

- Storage API availability  
- Backup failures  
- Missing or delayed backups (RPO violations)  

### ✅ Security & Access Control

This project includes a lightweight but realistic security simulation aligned with enterprise practices.

**API Token–Based RBAC**
The Storage API implements Role-Based Access Control (RBAC) using API tokens:

| Role   | Allowed Actions |
|-------|-----------------|
| read  | List volumes, list backups |
| backup| Trigger backups |
| admin | Create/delete volumes |

Tokens are provided via HTTP header:

X-API-TOKEN: <token>

Tokens are injected via environment variables:
- ADMIN_TOKEN
- BACKUP_TOKEN
- READ_TOKEN

### Secrets Management
Secrets are not hardcoded in the application logic. In production, these tokens should be stored securely using:
- Docker secrets
- Kubernetes Secrets
- Vault (HashiCorp)

### Transport & Encryption
- HTTPS termination is assumed at ingress / reverse proxy layer
- Backup metadata stored in MinIO (S3-compatible)
- Supports server-side encryption in real deployments

### Observability & Security Monitoring
Security-relevant signals are observable via Prometheus metrics:
- backup_failures_total
- backup_rpo_violation
- API availability via /health

These metrics can be alerted on using Prometheus Alertmanager or Grafana Alerting.

---

## Architecture Overview 

```
┌──────────────────────────────┐
│        Ansible AWX           │
│  Enterprise Control Plane    │
│ (Schedules & Workflows)      │
│ (Running on Kubernetes)      │
└─────────────┬────────────────┘
              │ Trigger Job Templates
┌─────────────▼───────────────┐
│      Automation Layer        │
│ (Ansible Execution Env)     │
│  - Dynamic Inventory        │
│  - Extra Vars / Secrets     │
└─────────────┬────────────────┘
              │ REST API Calls (X-API-TOKEN)
┌─────────────▼───────────────┐
│        Storage API           │
│  /volumes /backup /metrics  │
└─────────────┬────────────────┘
              │ S3 Operations
┌─────────────▼───────────────┐
│           MinIO              │
│   Volume Metadata / Backups  │
└─────────────┬────────────────┘
              │ Metrics Scrape
┌─────────────▼───────────────┐
│         Prometheus           │
│       Observability          │
└─────────────┬────────────────┘
              │ Dashboards
┌─────────────▼───────────────┐
│           Grafana            │
│   Real-time Visualization   │
└──────────────────────────────┘
```

---

## Quick Start – Full Lab Deployment

### 1. Start the complete environment

```bash
docker compose up -d --build
```

This will start:

- Storage API
- MinIO
- Backup Scheduler
- Prometheus
- Grafana
- Node Exporter

### 2. Access Components

| Component        | URL                         | Credentials           |
|------------------|-----------------------------|-----------------------|
| Storage API      | http://localhost:5000       | —                     |
| MinIO Console    | http://localhost:9001       | minio / minio123      |
| Prometheus       | http://localhost:9090       | —                     |
| Grafana          | http://localhost:3000       | admin / admin         |

---

## Automation Workflows (Ansible Playbooks)

In addition to the API-driven and scheduled operations, this project includes a set of **Ansible playbooks** that simulate day-to-day operational and lifecycle workflows typically executed by infrastructure or platform teams.

These playbooks demonstrate **repeatable, controlled automation** aligned with enterprise operational practices. It can be used both **standalone** and via **AWX Job Templates**.

### Available Playbooks

**Provision a new storage volume**
```bash
ansible-playbook ansible/playbooks/storage_provision.yml
```

**Trigger backups for all existing volumes**
```bash
ansible-playbook ansible/playbooks/backup_trigger.yml
```

**Validate backup availability and health**
```bash
ansible-playbook ansible/playbooks/backup_validate.yml
```

**Cleanup test volumes and backup artifacts**
```bash
ansible-playbook ansible/playbooks/cleanup.yml
```

**Simulate a Storage API lifecycle upgrade (LCM)**
```bash
ansible-playbook ansible/playbooks/lcm_upgrade.yml
```

**Run post-upgrade lifecycle health checks**
```bash
ansible-playbook ansible/playbooks/lcm_health_check.yml
```

These workflows illustrate how **configuration management and operational automation** integrate with API-driven platforms and observability systems.

---

## Grafana Dashboard

The Grafana dashboard reflects the **current production state** of the platform and is exported directly from Grafana.

📁 **Dashboard JSON**
```
monitoring/grafana/storage_backup_automation_dashboard.json
```

**Important Note on Time Semantics**
- The **Time** column represents Prometheus scrape time.
- The **Value** column represents the actual timestamp of the last successful backup.

This distinction is intentional and follows Prometheus best practices.

---

## Automated Scheduling & Notifications

### Backup Schedule
Automatic backups are managed via AWX Schedules.
- **Frequency:** Daily at 23:00.
- **Monitoring:** Visible in the AWX Dashboard with real-time job status tracking.

![AWX Daily Backup Overview](AWX-Daily-Backup.jpg)

Backup execution can be verified via:

- Scheduler logs (`/var/log/cron.log`)
- Prometheus metrics
- Grafana dashboard
- MinIO backup bucket contents

### Email Alerts
Integrated with **Gmail SMTP** to provide operational visibility:
- **Success Alerts:** Sent immediately after a successful backup workflow.
- **Failure Alerts:** Sent if any step in the lifecycle fails, including log links for rapid troubleshooting.

---

## What This Project Demonstrates

- API-first storage automation  
- Centralized automation using Ansible AWX  
- Decoupled backup orchestration  
- Health-aware scheduling and dependencies  
- Production-style observability and alerting  
- Enterprise RBAC and security patterns  

---

## Disclaimer

This project is a **simulation and learning platform**.  
It is not intended for direct production use, but the architecture and automation patterns align closely with real enterprise and telco environments.

---

👨‍💼 **Author**  
Thomas Waas
