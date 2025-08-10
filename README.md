# polymarket-playground

Paper-trading Polymarket server and client. Intended as a safe playground for automated trading, strategy prototyping, and offline backtesting without using real funds or accounts.

---

## Architecture

The system consists of two main components:

- **Server**: FastAPI backend for market synchronization, resolution, and webhook event emission.
- **Client**: Python library to interact with the server API for:
  - Creating users
  - Placing orders
  - Executing arbitrary SQL queries

---

## Typical Workflow

1. **Start the server** locally using `uvicorn`.
2. **Use the Python client** to interact with the backend for user and market operations.
3. **(Optional) Listen for webhook events** to trigger custom logic, such as:
   - Adding markets to a vector database
   - Running LLM-based strategies
   - Flagging untradable or resolved markets

---

## Getting Started

### Prerequisites

- **Python 3.12** (tested and recommended)
- `pip` for installing dependencies

### Installation

1. **Clone the repository**
    ```bash
    git clone https://github.com/navin-prasath-s/polymarket-playground
    cd polymarket-playground
    ```

2. **Create and activate a virtual environment**
    ```bash
    python -m venv .venv
    # On Linux / macOS:
    source .venv/bin/activate
    # On Windows:
    .venv\Scripts\activate
    ```

3. **Configuration**

    Create a `.env` file in the project root with the following keys:
    ```
    # Path to your SQLite database file
    DB_PATH=polymarket_playground.db

    # API keys for access control
    L1_KEY=abc
    L2_KEY=def

    # Webhook subscriber URL (for market events)
    SUBSCRIBER_URL=http://localhost:8001/market-event
    ```

4. **Install dependencies and run migrations**
    ```bash
    pip install -r requirements.txt
    alembic upgrade head
    ```
   
---

## Running the Server

Start the FastAPI backend:
```bash
uvicorn src.app:app --port 8000
```
- The API will be available at: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Interactive API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Using the Client

```python
from src.client.client import Client
client = Client(url="http://127.0.0.1:8000")
print(client.create_user(name="a"))
```
For more usage examples, see the [example notebook](`src/client/examples.ipynb`).


## Listening for Market Events

The server emits webhook events in real time when markets are added, resolved, or when payouts occur. You can use these events to trigger custom logic in your application.

### How It Works

- The server sends HTTP POST requests (webhooks) to your listener whenever a market event happens.
- You can handle these events by:
  - Using the provided example listener script, which prints events to the console.
  - Creating your own handler by subclassing the `MarketEventHandler` class.

### Event Types

- **`market_added`** – New markets have been created.
- **`market_resolved`** – Markets have been resolved with winning outcomes.
- **`payout_logs`** – Payout information for users.

### Quick Start

1. **Run the example listener** to see incoming events:
    ```bash
    python src/client/example_market_event_handler.py
    ```
    This script will print all received market events to the console.

2. **Customize event handling** by creating your own class that inherits from `MarketEventHandler` and implements the event methods.

For more details, see the code in `src/client/webhook_listener.py` and `src/client/example_market_event_handler.py`.
