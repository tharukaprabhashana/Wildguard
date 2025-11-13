# llm_gateway.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os, json

load_dotenv()

app = FastAPI(title="CrewAI LLM Gateway")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model = os.getenv("LLM_MODEL", "gpt-4-turbo")

class AgentRequest(BaseModel):
    agent: str
    prompt: str
    context: dict

@app.post("/run_agent")
async def run_agent(req: AgentRequest):
    print(f"[Gateway] Received request for agent: {req.agent}")
    # Add instruction to respond in JSON format
    system_prompt = req.prompt
    if "json" not in system_prompt.lower():
        system_prompt += "\n\nIMPORTANT: You must respond with valid JSON format only."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(req.context)}
    ]
    
    print(f"[Gateway] Calling OpenAI for {req.agent}...")
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"}
    )
    
    raw_content = completion.choices[0].message.content
    print(f"[Gateway] Received raw response ({len(raw_content)} chars)")
    
    try:
        data = json.loads(raw_content)
        print(f"[Gateway] ✓ Parsed JSON successfully, keys: {list(data.keys())}")
    except Exception as e:
        print(f"[Gateway] ✗ JSON parse error: {e}")
        data = {"result": raw_content}
    
    return {"result": data}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting LLM Gateway on http://0.0.0.0:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
