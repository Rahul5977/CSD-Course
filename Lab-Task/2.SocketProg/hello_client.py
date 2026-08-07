import asyncio
import websockets

SERVER_URI = "ws://10.50.52.215:8765"


async def send_hello():
    async with websockets.connect(SERVER_URI) as ws:
        # ddos attack
        for i in range(100):
            await ws.send("Leaked")
        print("Sent: Leaked")

        response = await ws.recv()
        print("Received:", response)


if __name__ == "__main__":
    asyncio.run(send_hello())
