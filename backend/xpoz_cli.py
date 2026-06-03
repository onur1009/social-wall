import sys
import json
from typing import List, Dict, Any

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Missing args"}))
        sys.exit(1)
        
    platform = sys.argv[1]
    keyword = sys.argv[2]
    api_key = "e1acfca5-62fe-4df1-9384-cb9d9c226dc8"
    
    try:
        from xpoz import XpozClient
        client = XpozClient(api_key=api_key, check_update=False)
        
        if platform == "twitter":
            result = client.twitter.search_posts(keyword, limit=8)
        elif platform == "instagram":
            result = client.instagram.search_posts(keyword, limit=8)
        else:
            print(json.dumps({"error": f"Unknown platform {platform}"}))
            sys.exit(1)
            
        items = []
        if hasattr(result, 'items'):
            items = result.items
        elif hasattr(result, 'data'):
            items = result.data
        elif isinstance(result, list):
            items = result
            
        # Serialize to dicts
        out_items = []
        for item in (items or []):
            if hasattr(item, 'model_dump'):
                out_items.append(item.model_dump())
            elif isinstance(item, dict):
                out_items.append(item)
            else:
                out_items.append(item.__dict__)
                
        print(json.dumps({"status": "ok", "items": out_items}, ensure_ascii=False))
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
