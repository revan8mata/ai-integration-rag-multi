# import httpx
# import asyncio
#
# async def test_stream():
#     async with httpx.AsyncClient() as client:
#         async with client.stream("POST", "http://localhost:8000/talk",
#             json={"content": "can you give me a briefing on this game?"},
#             headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoyLCJleHAiOjE3ODI2Njg1ODB9.p77ERbh4qz5Fj3bEI16FzXL97o_XOIT6R1PB38siIlw"}
#         ) as response:
#             async for chunk in response.aiter_text():
#                 print(chunk, end="", flush=True)
#
# asyncio.run(test_stream())