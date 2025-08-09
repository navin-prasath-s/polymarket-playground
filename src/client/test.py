from client import Client

# client = Client(url="http://127.0.0.1:8000", l1_key="abc", allow=("L1", ))
# print(client.reset_user_balance("pc1"))



client = Client(url="http://127.0.0.1:8000")
client.create_user("pc1", balance="100.50")
