# AI INTELLIGENCE ZONE — Control Arena
## Production-Grade System Architecture Document
### Version 2.0 | March 2026

---

## 1. SYSTEM ARCHITECTURE DIAGRAM

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        AI INTELLIGENCE ZONE — CONTROL ARENA                      │
│                           Production Architecture v2.0                            │
└──────────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   CLOUDFLARE     │
                              │   WAF + DDoS     │
                              │   Protection     │
                              └────────┬────────┘
                                       │
                              ┌────────▼────────┐
                              │   NGINX REVERSE  │
                              │   PROXY + SSL    │
                              │   Rate Limiter   │
                              └────────┬────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
           ┌────────▼──────┐  ┌───────▼───────┐  ┌──────▼───────┐
           │  ADMIN PANEL  │  │  TEAM PORTAL  │  │  PUBLIC      │
           │  (React/Next) │  │  (React SPA)  │  │  LEADERBOARD │
           │  Port 3000    │  │  Port 3001    │  │  Port 3002   │
           └────────┬──────┘  └───────┬───────┘  └──────┬───────┘
                    │                 │                  │
                    └─────────────────┼──────────────────┘
                                      │
                              ┌───────▼───────┐
                              │   API GATEWAY  │
                              │   Flask App    │
                              │   Port 5000    │
                              │   ┌─────────┐  │
                              │   │  Auth    │  │
                              │   │  Middle  │  │
                              │   │  ware    │  │
                              │   └─────────┘  │
                              └───────┬───────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
     ┌────────▼──────┐      ┌────────▼──────┐      ┌────────▼──────┐
     │  CORE ENGINE  │      │  AI VALIDATION│      │  SECURITY     │
     │               │      │  ENGINE       │      │  ENGINE       │
     │ • Team Mgmt   │      │               │      │               │
     │ • Missions    │      │ • JSON Schema │      │ • Injection   │
     │ • Scoring     │      │ • Regex Valid  │      │   Detection   │
     │ • Leaderboard │      │ • Type Check  │      │ • Rate Limit  │
     │ • Submissions │      │ • Confidence  │      │ • Audit Log   │
     └────────┬──────┘      └────────┬──────┘      └────────┬──────┘
              │                       │                       │
              └───────────────────────┼───────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
           ┌────────▼──────┐ ┌───────▼───────┐ ┌──────▼───────┐
           │  PostgreSQL   │ │    Redis      │ │  InfluxDB    │
           │  Primary DB   │ │  Cache +      │ │  Time Series │
           │               │ │  Sessions +   │ │  Metrics     │
           │ • Teams       │ │  Pub/Sub      │ │              │
           │ • Users       │ │               │ │ • Latency    │
           │ • Missions    │ │ • Leaderboard │ │ • Throughput │
           │ • Submissions │ │ • Rate Limits │ │ • Error Rate │
           │ • Audit Logs  │ │ • Live Feed   │ │ • Anomalies  │
           └───────────────┘ └───────────────┘ └──────────────┘
                    │
           ┌────────▼──────┐
           │  BACKUP       │
           │  S3/MinIO     │
           │               │
           │ • DB Dumps    │
           │ • Audit Logs  │
           │ • Exports     │
           └───────────────┘

    ┌──────────────────────────────────────────────────┐
    │              REAL-TIME LAYER                      │
    │                                                   │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
    │  │ Socket.IO│  │ SSE Feed │  │ WebHooks │       │
    │  │          │  │          │  │          │       │
    │  │ Live     │  │ Leader-  │  │ Alert    │       │
    │  │ Activity │  │ board    │  │ Notifs   │       │
    │  │ Monitor  │  │ Stream   │  │          │       │
    │  └──────────┘  └──────────┘  └──────────┘       │
    └──────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────┐
    │            OBSERVABILITY STACK                    │
    │                                                   │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
    │  │Prometheus│  │ Grafana  │  │ Sentry   │       │
    │  │ Metrics  │  │ Dashbrd  │  │ Error    │       │
    │  │          │  │          │  │ Tracking │       │
    │  └──────────┘  └──────────┘  └──────────┘       │
    └──────────────────────────────────────────────────┘
```

---

## 2. DATA FLOW DIAGRAM

```
TEAM SUBMITS PROMPT
        │
        ▼
┌───────────────┐     ┌───────────────┐
│ Rate Limiter  │────▶│ Auth Check    │
│ (Redis Token  │     │ (JWT + RBAC)  │
│  Bucket)      │     └───────┬───────┘
└───────────────┘             │
                              ▼
                    ┌───────────────┐
                    │ Injection     │
                    │ Detection     │
                    │ Engine        │
                    └───────┬───────┘
                            │
                   CLEAN ───┤──── FLAGGED
                     │              │
                     ▼              ▼
              ┌────────────┐ ┌────────────┐
              │ AI Process │ │ Quarantine │
              │ Pipeline   │ │ + Alert    │
              └─────┬──────┘ └────────────┘
                    │
                    ▼
           ┌───────────────┐
           │ Response      │
           │ Validation    │
           │ Engine        │
           │               │
           │ 1. JSON Parse │
           │ 2. Schema     │
           │ 3. Type Check │
           │ 4. Regex      │
           │ 5. Confidence │
           └───────┬───────┘
                   │
          PASS ────┤──── FAIL
            │              │
            ▼              ▼
     ┌────────────┐ ┌────────────┐
     │ Score      │ │ Error Log  │
     │ Calculator │ │ + Retry    │
     │ + Board    │ │ Counter    │
     └────────────┘ └────────────┘
            │
            ▼
     ┌────────────┐
     │ Leaderboard│
     │ Cache      │
     │ Invalidate │
     └────────────┘
```

---

## 3. TECH STACK

| Layer | Technology | Justification |
|-------|-----------|---------------|
| **Backend API** | Flask + Flask-SocketIO | Lightweight, extensible, real-time capable |
| **Database** | PostgreSQL 16 | ACID compliance, JSON support, robust |
| **Cache** | Redis 7 | Leaderboard, sessions, rate limiting, pub/sub |
| **Time-Series** | InfluxDB | Activity metrics, anomaly detection |
| **Task Queue** | Celery + Redis | Async scoring, batch exports, alerts |
| **Admin Frontend** | HTML/CSS/JS (Jinja2) | Server-rendered, fast, no build step needed |
| **Real-Time** | Socket.IO | Bi-directional, fallback to polling |
| **Auth** | JWT + Flask-Login | Stateless API auth + session admin |
| **Validation** | jsonschema + custom | Schema enforcement, regex, type checking |
| **Security** | Custom middleware | Injection detection, RBAC, audit trail |
| **Monitoring** | Prometheus + Grafana | Metrics, dashboards, alerting |
| **Error Tracking** | Sentry | Production error capture |
| **Containerization** | Docker + Compose | Reproducible deployment |
| **Reverse Proxy** | Nginx | SSL termination, rate limiting |
| **Backup** | pg_dump + S3/MinIO | Scheduled backups, log archival |

---

## 4. SECURITY STRATEGY

### 4.1 Defense-in-Depth Model

```
Layer 1: Network     → Nginx rate limit, IP whitelist, SSL/TLS
Layer 2: Application → JWT auth, RBAC, CORS, CSRF protection
Layer 3: Logic       → Input validation, injection detection, schema enforcement
Layer 4: Data        → Encrypted at rest, parameterized queries, audit logs
Layer 5: Monitoring  → Anomaly detection, real-time alerts, tamper detection
```

### 4.2 Prompt Injection Detection

The system uses a multi-layered approach:

1. **Pattern Matching**: Known injection patterns (ignore instructions, system prompt leaks)
2. **Entropy Analysis**: Unusually high entropy strings flagged
3. **Length Anomaly**: Prompts exceeding statistical norms flagged
4. **Frequency Analysis**: Rapid-fire submissions detected and throttled
5. **Semantic Similarity**: Repeated near-identical prompts flagged
6. **Nested Command Detection**: SQL, OS command, path traversal patterns

### 4.3 Rate Limiting Strategy

| Endpoint | Window | Max Requests | Burst |
|----------|--------|-------------|-------|
| `/api/submit` | 60s | 10 | 3 |
| `/api/leaderboard` | 10s | 30 | 10 |
| `/api/team/*` | 60s | 20 | 5 |
| `/admin/*` | 60s | 100 | 20 |

### 4.4 Audit Trail

Every action is logged with:
- Timestamp (UTC, microsecond precision)
- Actor (user_id, team_id, role)
- Action type
- Resource affected
- IP address
- User agent
- Request payload hash
- Response status
- Geo-location (from IP)

---

## 5. LEADERBOARD SCORING ALGORITHM

### 5.1 Base Score Formula

```
Mission_Score = (Accuracy × W_acc) + (Speed_Bonus × W_spd) + (Validation_Rate × W_val)

Where:
  W_acc = 0.50  (50% weight — correctness is king)
  W_spd = 0.20  (20% weight — faster completion rewarded)
  W_val = 0.30  (30% weight — clean, valid responses matter)
```

### 5.2 Accuracy Score (0-100)

```
Accuracy = (Correct_Fields / Total_Fields) × 100
         × Schema_Compliance_Multiplier
         × Confidence_Score

Schema_Compliance_Multiplier:
  1.0 = Perfect schema match
  0.8 = Minor deviations (extra fields)
  0.5 = Major deviations (missing required fields)
  0.0 = Invalid JSON / unparseable
```

### 5.3 Speed Bonus (0-100)

```
Speed_Bonus = max(0, 100 - ((Time_Taken / Time_Limit) × 100))

With decay: Speed_Bonus × e^(-λ × attempts)
Where λ = 0.1 (penalizes excessive retries)
```

### 5.4 Validation Rate (0-100)

```
Validation_Rate = (Successful_Validations / Total_Submissions) × 100
```

### 5.5 Bonus Scoring

| Bonus Type | Points | Condition |
|-----------|--------|-----------|
| First Blood | +50 | First team to complete a mission |
| Perfect Parse | +25 | Zero validation errors on first try |
| Speed Demon | +30 | Complete in under 25% of time limit |
| Consistency | +20 | 5 consecutive valid submissions |
| Zero Error | +40 | Complete all missions with 0 errors |
| Innovation | +15 | Creative prompt engineering (admin judged) |

### 5.6 Tie-Break Logic

```
Priority Order:
1. Total score (highest wins)
2. Fewer total submissions (efficiency)
3. Earlier final submission timestamp
4. Higher average confidence score
5. Lower hallucination rate
6. Admin manual override (last resort)
```

### 5.7 Anti-Gaming Measures

- Exponential decay on retry scores
- Minimum time between submissions enforced
- Copy-paste detection across teams
- Statistical outlier detection (impossibly fast/perfect)
- Admin can freeze scores pending investigation

---

## 6. CREATIVE ENHANCEMENTS

### 6.1 🎮 Live Battle Mode
Real-time head-to-head mission where two teams race simultaneously, visible to all on the projector dashboard.

### 6.2 🧠 Hallucination Heatmap
Visual heatmap showing which parts of AI responses tend to hallucinate across all teams — valuable research data.

### 6.3 🏆 Achievement System
Unlock badges: "JSON Ninja", "Speed Demon", "Zero Error Streak", "Comeback King" — displayed on team profiles.

### 6.4 📊 Team Health Score
Composite metric combining activity, error rate, submission quality, and participation — visible to admins for early intervention.

### 6.5 🔍 Forensic Replay
Admin can replay a team's entire session chronologically — every prompt, response, validation — like a DVR for debugging disputes.

### 6.6 🚨 Smart Alert System
ML-based anomaly detection alerts admins when:
- A team's behavior deviates from baseline
- Submission patterns suggest automation
- Score jumps are statistically improbable

### 6.7 📡 Spectator Mode
Public-facing dashboard for audience engagement showing live stats, top teams, and activity feed without sensitive data.

### 6.8 🧪 Sandbox Mode
Pre-competition practice environment where teams can test prompts without affecting scores or leaderboard.

---

## 7. DEPLOYMENT STRATEGY

### 7.1 Docker Compose Stack

```
services:
  nginx          → Reverse proxy + SSL
  flask-api      → 3 replicas behind load balancer
  celery-worker  → 2 workers for async tasks
  celery-beat    → Scheduled tasks (backups, cleanup)
  postgres       → Primary database
  redis          → Cache + message broker
  influxdb       → Time-series metrics
  grafana        → Monitoring dashboards
  prometheus     → Metrics collection
```

### 7.2 Pre-Competition Checklist

- [ ] Load test with 150+ simulated teams
- [ ] Verify all rate limits under stress
- [ ] Test failover scenarios
- [ ] Verify backup/restore cycle
- [ ] Security audit (injection tests)
- [ ] Admin panel walkthrough
- [ ] Emergency shutdown procedure documented
- [ ] Network isolation verified
- [ ] Clock synchronization confirmed (NTP)
- [ ] Emergency contact list distributed
