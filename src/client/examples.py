from client import Client

# Create a client instance
client = Client(url="http://127.0.0.1:8000")
client_l1 = Client(url="http://127.0.0.1:8000", l1_key="abc")
client_l2 = Client(url="http://127.0.0.1:8000", l2_key="def")
client_all = Client(url="http://127.0.0.1:8000", l1_key="abc", l2_key="def")


# Create a user
response = client.create_user("pc1", balance="1080.50")
name = response["name"]


# Get the user
client.get_user(name)


# Reset balance - need l1 authorized client
client_l1.reset_user_balance(name, "500.00")


# Buy shares
client.buy(
    user_name=name,
    market="0xcccb7e7613a087c132b69cbf3a02bece3fdcb824c1da54ae79acc8d4a562d902",
    token="8441400852834915183759801017793514978104486628517653995211751018945988243154",
    amount_usdc="400.00"
)


# Sell a shares
client.sell(
    user_name=name,
    market="0xcccb7e7613a087c132b69cbf3a02bece3fdcb824c1da54ae79acc8d4a562d902",
    token="8441400852834915183759801017793514978104486628517653995211751018945988243154",
    shares="1.00"
)


# Get list of all orders
client.list_orders()


# Get all orders placed by specific client
client.list_orders_by_user(name)


# Get list of all user positions
client.list_positions()


# Get user position by username
client.list_positions_by_user(name)


# Delete all entries in the database - Needs l2 auth
client_l2.delete_all_data()


# Arbitrary SQL execution - Needs l2 auth
client_l2.exec_sql(
    "SELECT * FROM users",
    limit=100,
)
