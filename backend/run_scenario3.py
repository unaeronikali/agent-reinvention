from dotenv import load_dotenv
load_dotenv("../.env")

import asyncio
import db
import executor
import mcp_client

i = db.create_incident(
    3,
    db.get_scenario(3)["affected_resource_id"]
)

async def go():
    await executor.run_incident(i, auto_approve=True)
    await mcp_client.close()

asyncio.run(go())

print("final:", db.get_incident(i)["status"])