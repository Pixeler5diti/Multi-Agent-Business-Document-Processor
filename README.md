# 🧠 Multi-Agent Business Document Processor

An intelligent multi-agent system that ingests documents in **Email**, **JSON**, and **PDF** formats, classifies their **format and business intent**, routes them to specialized agents, and dynamically triggers follow-up actions like alerts, escalations, or summaries — all backed by **LLM (Gemini)** and **PostgreSQL**.

## Architecure Diagram
![- visual selection](https://github.com/Pixeler5diti/Multi-Agent-Business-Document-Processor/blob/97ebef5984aea29c0a408e23233b02a8990d9ebd/assests/-%20visual%20selection.png)

## System Preview :
### Home Page:
![1](https://github.com/Pixeler5diti/Multi-Agent-Business-Document-Processor/blob/8a6b7c9e298acbf4c30fdd006722fdbfbdfbb6ee/assests/1.png)

### Claasification of file and action taken
![2](https://github.com/Pixeler5diti/Multi-Agent-Business-Document-Processor/blob/8a6b7c9e298acbf4c30fdd006722fdbfbdfbb6ee/assests/2.png)

---

## 🚀 Features

- **Multi-format Support**: Ingests Email, JSON webhooks, and PDF documents.
- **Business Intent Detection**: Identifies intents like RFQ, Complaint, Invoice, Regulation, or Fraud Risk.
- **Dynamic Agent Routing**: Based on classification, data is routed to Email, JSON, or PDF agent.
- **Action Chaining**: Follows up with API calls (simulated) like escalating complaints or flagging risks.
- **Shared Memory Store**: Centralized decision logging, agent traces, and metadata.
- **Simple Web UI**: Upload files and observe real-time classification and action.
- **Dockerized**: Fully containerized for easy deployment.
- **Retry Logic**: Robustness in case agent actions fail.

---

## 🧩 Build Components

### 1. 🧠 Classifier Agent
- Detects document `format` and `business intent`
- Supports formats: `Email`, `JSON`, `PDF`
- Intents: `RFQ`, `Complaint`, `Invoice`, `Regulation`, `Fraud Risk`
- Techniques:
  - Few-shot prompting using **Gemini API**
  - Schema matching
- Passes routing metadata to memory store

---

### 2. 📩 Email Agent
- Extracts:
  - `sender`, `urgency`, `request/issue`
  - `tone`: polite, angry, threatening
- Logic:
  - If `tone=threatening` or `urgency=high` → POST `/crm/escalate`
  - Else → log and close

---

### 3. 🧬 JSON Agent
- Parses simulated webhook data
- Validates required schema fields
- Flags:
  - Missing fields
  - Type mismatches
- On anomaly → log to memory/API

---

### 4. 📄 PDF Agent
- Uses **PDF parsers** (e.g., Tika, PyPDF2)
- Supports:
  - Invoices (line-items, totals)
  - Policies
- Flags:
  - Invoice total > 10,000
  - Mentions of `GDPR`, `FDA`, etc.

---

### 5. 🧠 Shared Memory Store
All agents log to a central store:
- Classification output
- Extracted fields
- Follow-up actions
- Timestamps + source trace

---

### 6. 🔁 Action Router
Dynamically triggers actions:
- Routes to:
  - `/crm` for escalation
  - `/risk_alert` for compliance
- Simulated via REST

---

## 🔁 End-to-End Example
- User uploads email

- Classifier: Format = Email, Intent = Complaint

- Email Agent: Tone = Angry, Urgency = High

- Action Router: Calls POST /crm/escalate

- Memory logs the entire trace for audit


---

## 🛠️ Tech Stack

| Layer         | Tool / Library              |
|---------------|-----------------------------|
| Language      | Python 3.11+                |
| Framework     | FastAPI                     |
| LLM           | Gemini API (via LangChain)  |
| PDF Parsing   | Tika / PyPDF2               |
| Database      | PostgreSQL (via SQLAlchemy) |
| Memory Store  | SQLite (optional Redis)     |
| Web UI        | HTML + CSS + JS             |
| Container     | Docker + Docker Compose     |
| Retry Logic   | Built-in backoff (utils)    |

---

## 🧪 Project Structure

```
.
├── agents/ # Classifier, Email, JSON, PDF agents
├── scripts/ # Init SQL, wait-for-it.sh
├── services/ # Action router, memory store
├── static/ # UI files (index.html, CSS/JS)
├── utils/ # Retry logic
├── main.py # FastAPI app
├── models.py # Pydantic models
├── database.py # PostgreSQL DB models
├── .env.example # Env template (API keys etc.)
├── Dockerfile # Docker build
├── docker-compose.yml # Multi-container setup
└── nginx.conf # Optional: serve UI via NGINX
```

---

## ⚙️ Setup & Run

### 1. Clone

```
git clone https://github.com/your-repo/multi-agent-doc-processor
cd multi-agent-doc-processor
```
### 2. Run this on your system
```
python main.py
```

