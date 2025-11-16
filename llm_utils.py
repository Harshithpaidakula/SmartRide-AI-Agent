from typing import Dict, Any
import json
import openai

async def parse_nlu(text: str) -> Dict[str, Any]:
    prompt = f"""
Extract pickup, drop, and vehicle priority order from the user's message.
Return JSON ONLY: {{"pickup":"...","drop":"...","priority":["auto","cab","bike"]}}
Example: "Pickup at MG Road, drop at Banjara Hills. Prefer Auto then Cab." -> {{"pickup":"MG Road","drop":"Banjara Hills","priority":["auto","cab"]}}
User: "{text}"
"""
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.0,
        max_tokens=150
    )
    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        raise ValueError("NLU parse failed - use structured form.")
