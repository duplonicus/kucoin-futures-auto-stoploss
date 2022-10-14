import asyncio
from surrealdb.clients.http import HTTPClient

# SurrealDB HTTP Client Object
client = HTTPClient(
    "http://localhost:8000",
    namespace="kucoin",
    database="kucoin",
    username="root",
    password="root",
)

event_loop = asyncio.get_event_loop()

async def create_all(table, data):
    """Create a table and add data."""
    response = await client.create_all(table, data)
    print(response)

async def create_with_id(table, custom_id, data):
    """
    Create a record with a specified id.
    This will raise an exception if the record already exists.
    """
    response = await client.create_one(table, custom_id, data)
    print(response)

async def select_all(table):
    """Query a table for all records."""
    response = await client.select_all(table)
    print(response)

async def select_one(table, custom_id):
    """Query a table for a specific record by the record's id."""
    response = await client.select_one(table, custom_id)
    print(response)

async def replace_one(table, custom_id, new_data):
    """Replace a record with a specified id."""
    response = await client.replace_one(table, custom_id, new_data)
    print(response)

async def upsert_one(table, custom_id, partial_new_data):
    """Patch a record with a specified id."""
    response = await client.upsert_one(table, custom_id, partial_new_data)
    #print(response)

async def delete_all(table):
    """Delete all records in a table."""
    await client.delete_all(table)

async def delete_one(table, custom_id):
    """Delete a record with a specified id."""
    await client.delete_one(table, custom_id)

async def my_query(query):
    """Execute a custom query."""
    response = await client.execute(query)
    print(response)

if __name__ == "__main__":
    event_loop.run_until_complete(select_all("symbol"))