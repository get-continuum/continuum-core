# Engram Semantic — "The Context Layer"

**Engram** (Pitching as **Axiom.ai** or **Ontix.ai**) is a Semantic Router for AI Agents.
It solves the "Last Mile" problem of analytics by adding **Context** to your Data Warehouse.

## 🚀 The MVP: 3 Core Pillars
We have built a fully functional prototype demonstrating:

### 1. 🧠 The Brain (LLM Resolver)
*   **Problem**: Users ask vague questions like *"How much cash did we burn?"*.
*   **Solution**: Engram uses an LLM (OpenAI) to map "burn" → `finance.expenses` or `marketing.spend` based on **User Context**.
*   **Code**: `scripts/llm_resolver.py`

### 2. 💾 The Memory (Active Learning)
*   **Problem**: AI models hallucinate or guess wrong.
*   **Solution**: When you clarify ambiguity (e.g., *"By bookings, I mean Marketing Bookings"*), Engram **remembers** it.
*   **Code**: `scripts/demo_lib.py` (Active Learning Logic), `demo/user_aliases.json` (Persistence).

### 3. 🧬 The Trust (Lineage)
*   **Problem**: CEOs don't trust black-box AI answers.
*   **Solution**: Engram shows the **Breadcrumbs**: `User Query` → `Context` → `Reasoning` → `Source YAML`.
*   **Code**: `scripts/interactive_demo.py` (Visualizer).

---

## 🎮 How to Run the Demo

### 1. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install openai streamlit watchdog
```

### 2. Run the Interactive App
```bash
.venv/bin/streamlit run scripts/interactive_demo.py
```
*   **Enter OpenAI API Key** in the sidebar to unlock the "Brain".
*   **Without Key**: It falls back to a "Mock Brain" (keywords) for safe demos.

### 3. Demo Flow
1.  **Setup**: Show the conflicting YAMLs in the sidebar (`paid_metrics.yaml`, `finance.yaml`).
2.  **Context**: Switch between "Marketing" and "Finance" to see the answer change.
3.  **Brain**: Ask *"How much cash did we burn?"*.
4.  **Memory**: Switch to "Unknown", ask *"Show Bookings"*, and use the **"Remind me?"** checkbox.

---

## 📂 Project Structure
*   `scripts/interactive_demo.py`: The main Streamlit App.
*   `scripts/demo_lib.py`: The Business Logic (Engine).
*   `scripts/llm_resolver.py`: The AI Integration.
*   `app/db/models.py`: Production-ready Postgres Schema (Supabase compatible).
*   `demo/`: Sample Semantic Models (YAMLs).
