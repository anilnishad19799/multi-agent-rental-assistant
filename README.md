# 🏠 Multi-Agent Real Estate & Rental Assistant

An autonomous, multi-agent AI rental assistant designed to search PG/flat rentals, collect customer profiles, and book visit appointments in real-time. Built with **FastAPI**, **Async SQLAlchemy**, and **Server-Sent Events (SSE)**, supporting multiple LLM providers (Groq, OpenAI, Google Gemini).

---

## 🌟 Key Features

- **Multi-Agent Architecture**:
  - **Supervisor Agent**: Intelligent intent classification and query routing.
  - **Rent Agent**: Property search, criteria collection, and real-time database querying.
  - **User Info Agent**: Profile collection with single-form data extraction and visual review.
  - **Calendar Agent**: Appointment slot suggestion, conflict checks, and interactive booking cards.
  - **General Agent**: System navigation, help, and greeting handling.

- **Dual-Layer Memory System**:
  - **Short-Term Memory (`ThreadMemory`)**: Thread-safe in-memory buffer with session-scoped sliding window, working memory, and user attention tracking.
  - **Long-Term Memory (`LongTermMemory`)**: Persistent database storage comprising:
    - *Semantic Memory*: Known user and property facts.
    - *Episodic Memory*: Conversation history and agent handoff timeline.
    - *Procedural Memory*: Learned user preferences and behavioral flow patterns.

- **Real-Time Streaming & Interactive UI**:
  - SSE-powered live streaming (`/api/stream/{session_id}`).
  - Dynamic HTML tables for property listings, user profile reviews, and available appointment slots.
  - Interactive clickable time-slot pills for frictionless appointment booking.

- **Provider Agnostic**:
  - Switch between **Groq**, **OpenAI**, or **Google Gemini** on the fly via UI or configuration.

---

## 🏗️ Architecture Flow

```
User Query ──► /api/chat ──► Orchestrator
                                │
               ┌────────────────┴────────────────┐
               ▼                                 ▼
         Short-Term Memory               Long-Term Memory
         (Thread Buffer)                 (Semantic / Episodic / Procedural)
               │                                 │
               └────────────────┬────────────────┘
                                ▼
                         Supervisor Agent
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
    Rent Agent           User Info Agent          Calendar Agent
 (Search & Filter)     (Profile Collection)     (Slot Booking & Visit)
        │                       │                       │
        └───────────────────────┴───────────────────────┘
                                ▼
                       Server-Sent Events (SSE)
                                ▼
                        Web Chat Frontend
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10+ (or Conda environment)
- API key for at least one LLM provider (Groq, OpenAI, or Gemini)

### 2. Clone Repository
```bash
git clone https://github.com/<your-username>/real-estate-ai-agent.git
cd real-estate-ai-agent
```

### 3. Create & Activate Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env` and provide your API keys:
```bash
cp .env.example .env
```
Edit `.env`:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=sqlite+aiosqlite:///./rental_system.db
```

### 6. Seed Sample Database (Optional)
```bash
python scripts/seed_db.py
```

### 7. Run the Application
```bash
uvicorn backend.main:app --reload --port 8000
```
Open your browser and navigate to:
👉 **`http://localhost:8000`**

---

## 📂 Project Structure

```
├── backend/
│   ├── agents/           # Specialized agent definitions and prompts
│   │   ├── supervisor_agent.py
│   │   ├── rent_agent.py
│   │   ├── user_info_agent.py
│   │   ├── calendar_agent.py
│   │   └── prompts.py
│   ├── api/              # FastAPI endpoints (routes, SSE streaming)
│   ├── core/             # Orchestrator & state management
│   ├── events/           # Event definitions & publisher
│   ├── memory/           # Short-term, long-term, semantic, episodic, procedural
│   ├── models/           # SQLAlchemy database schemas
│   ├── repositories/     # Data access layer for properties, bookings, users
│   └── services/         # LLM clients (OpenAI, Groq, Gemini)
├── frontend/             # Browser client (HTML5, Vanilla JS, CSS3)
├── scripts/              # Seed scripts, memory tests, benchmarks
├── tests/                # Pytest test suites
├── requirements.txt      # Python dependencies
└── README.md
```

---

## 🧪 Testing

Run memory and orchestration unit tests:
```bash
python scripts/test_memory.py
```

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
