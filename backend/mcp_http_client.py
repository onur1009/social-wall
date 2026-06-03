import asyncio
import httpx
import json
from typing import Dict, Any, List

class DirectXpozClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://mcp.xpoz.ai/mcp"
        self.post_url = None
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
    async def initialize(self):
        """SSE baglantisi kurar ve POST URL'i alir."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = self.headers.copy()
            headers["Accept"] = "text/event-stream"
            
            try:
                # Akisi manuel okuyoruz
                async with client.stream("GET", self.base_url, headers=headers) as resp:
                    if resp.status_code != 200:
                        raise Exception(f"HTTP {resp.status_code}")
                        
                    buffer = ""
                    async for chunk in resp.aiter_text():
                        buffer += chunk
                        while '\n\n' in buffer:
                            msg, buffer = buffer.split('\n\n', 1)
                            
                            event = None
                            data = ""
                            for line in msg.split('\n'):
                                if line.startswith('event: '):
                                    event = line[7:].strip()
                                elif line.startswith('data: '):
                                    data = line[6:].strip()
                            
                            if event == "endpoint" or (not event and 'message?session=' in data):
                                # Endpoint alindi
                                if data.startswith('/'):
                                    self.post_url = "https://mcp.xpoz.ai" + data
                                else:
                                    self.post_url = data
                                return True
            except Exception as e:
                print(f"[DirectXpoz] SSE hatasi: {e}")
                return False
        return False
        
    async def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.post_url:
            raise Exception("Client not initialized")
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.post_url, json=payload, headers=self.headers)
            if resp.status_code != 200 and resp.status_code != 202:
                raise Exception(f"POST error: {resp.status_code} - {resp.text}")
            
            # Sunucu yaniti
            # Eger HTTP ise genelde bos donebilir ve cevabi SSE uzerinden verir!
            # xpoz mcp sunucusu post isteklerine yanit veriyor mu?
            return resp.json()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> List[Any]:
        if not self.post_url:
            success = await self.initialize()
            if not success:
                raise Exception("Failed to initialize SSE")
                
        # 1. Initialize
        init_payload = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "social-wall", "version": "1.0"}
            }
        }
        await self._send_request(init_payload)
        
        # 2. Notified
        notif_payload = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        await self._send_request(notif_payload)
        
        # 3. Tool Call
        tool_payload = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        }
        
        # xpoz'un HTTP MCP uygulamasi sonuclari POST yanitinda JSON olarak donuyor.
        resp_data = await self._send_request(tool_payload)
        
        # Check error
        if "error" in resp_data:
            raise Exception(f"API Error: {resp_data['error']}")
            
        result = resp_data.get("result", {})
        content = result.get("content", [])
        
        all_items = []
        for c in content:
            if c.get("type") == "text":
                parsed = json.loads(c["text"])
                items = parsed.get("items", parsed.get("data", parsed.get("posts", [])))
                if not items and isinstance(parsed, list):
                    items = parsed
                all_items.extend(items)
                
        return all_items

async def test():
    client = DirectXpozClient("e1acfca5-62fe-4df1-9384-cb9d9c226dc8")
    res = await client.call_tool("getTwitterPostsByKeywords", {"keywords": ["bitcoin"], "limit": 2})
    print("Tweetler:", len(res))

if __name__ == "__main__":
    asyncio.run(test())
