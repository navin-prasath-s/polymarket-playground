# polymarket-playground



## Architecture

The system is split into two independent parts:

- **Server** – FastAPI backend for market synchronization, resolution, and webhook emission.
- **Client** – Python library to interact with the server API for:
  - Creating users
  - Placing orders
  - Executing arbitrary SQL

## Typical Workflow

1. **Run the server locally** using `uvicorn`.
2. **Use the Python client** to interact with the backend.
3. **Optionally listen for webhook events** to trigger custom logic such as:
   - Adding markets to your vector database
   - Running LLM-based strategies
   - Flagging untradable or resolved markets


## Getting Started

### Prerequisites

- **Python 3.12** (tested and recommended)
- pip for installing dependencies

### Installation

1. **Clone the repository**
   ```bash
   https://github.com/navin-prasath-s/polymarket-playground
   cd polymarket-playground

2. **Create and activate a virtual environment**
    ```bash
    python -m venv .venv
    source .venv/bin/activate   # Linux / macOS
    .venv\Scripts\activate      # Windows

3. **Configuration**
    ```bash
    create a `.env` file in the project root with the following keys:
   
    # Path to your SQLite database file
    DB_PATH=polymarket_playground.db
   
    # API keys for access control
    L1_KEY=abc   
    L2_KEY=def     
   
    # Webhook subscriber URL (for market events)
    SUBSCRIBER_URL=http://localhost:8001/market-event
   
4. **Setup**
    ```
   pip install -r requirements.txt
   alembic upgrade head


### Running the Server
    uvicorn src.app:app --reload --port 8000
This starts the FastAPI backend at http://127.0.0.1:8000

Access the docs at http://127.0.0.1:8000/docs

### Using the Client
    from client import Client
    client = Client(url="http://127.0.0.1:8000")
    print(client.get_users())
More examples at src/client/examples.ipynb

## Listening for Market Events

The server emits webhook events for real-time market changes.  
You can either use the provided listener script **or** write your own.

### Quick Start (using built-in listener)

Run the built-in listener first:

```bash
python src/client/webhook_listener.py


   

