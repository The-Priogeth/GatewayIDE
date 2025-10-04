import asyncio, sys
from pathlib import Path
import grpc

BASE = Path(__file__).parent
sys.path.append(str(BASE))  # for generated *_pb2.py imports

import ai_service_pb2 as pb
import ai_service_pb2_grpc as rpc

class AIServiceImpl(rpc.AIServiceServicer):
    async def Echo(self, request, context):
        return pb.EchoReply(text=f"echo:{request.text}")

    async def ChatStream(self, request_iterator, context):
        async for msg in request_iterator:
            yield pb.ChatServerMsg(text=f"bot:{msg.text}")

async def serve():
    server = grpc.aio.server()
    rpc.add_AIServiceServicer_to_server(AIServiceImpl(), server)
    server.add_insecure_port('[::]:50051')
    await server.start()
    print("AIService listening on 0.0.0.0:50051", flush=True)
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
