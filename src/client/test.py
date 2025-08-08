from client import Client

client = Client(url="http://127.0.0.1:8000")
print(client.get_health())
