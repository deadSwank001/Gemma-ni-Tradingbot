"""Prompt query: is on line 12 """"
import requests
import json
from config import OLLAMA_HOST, LLM_MODEL

def query_gemma(market_context: str) -> dict:
    """
    Queries the local Ollama instance running gemma2 with the current TA context.
    Returns a structured dictionary with the decision.
    """
  
    prompt = f"""
You are an expert Solana crypto trading bot reasoning engine. 
Analyze the provided Technical Analysis metrics and decide whether to BUY, SELL, or HOLD the asset.

"""YOU CAN CHANGE THIS PROMPT ^^^ TO TWEAK IT HOW YOU WANT IT"""

Market Data Context:
{market_context}

Respond STRICTLY with a valid JSON block containing:
- "action": "BUY", "SELL", or "HOLD"
- "confidence": A score between 0 and 100
- "reasoning": A brief 1-2 sentence explanation of your decision based on the metrics.

Do not output any markdown formatting, just the raw JSON text.
"""
    
    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json" # Ollama feature for structured output
    }
    
    url = f"{OLLAMA_HOST}/api/generate"
    try:
        response = requests.post(url, json=payload) 'check for the tokens and respone'
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "{}")
            # In a robust system, add error handling and JSON cleaning here.
            return json.loads(response_text)
        else:
            print(f"[LLM Engine] Ollama error: {response.text}")
            return {"action": "HOLD", "confidence": 0, "reasoning": "LLM API Error"}
    except Exception as e:
        print(f"[LLM Engine] Exception calling Ollama: {e}")
        return {"action": "HOLD", "confidence": 0, "reasoning": "Exception encountered."}

