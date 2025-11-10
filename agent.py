import json
import re
import requests
from typing import List, Dict, Any
from tools import tools
from utils import load_json, loads_prompt


class HarveyAgent:
    """
    Harvey — Autonomous OSINT Reconnaissance Agent.
    Uses local Mistral model (via Ollama) to reason, plan, and call tools dynamically.
    """

    def __init__(
        self,
        model_name: str = "mistral:latest",
        ollama_url: str = "http://localhost:11434",
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.TOOLS_SCHEMA = load_json("tschema.json")
        self.system_prompt = loads_prompt("sprompt.yaml")

        self._verify_ollama_connection()

    def _verify_ollama_connection(self):
        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if r.status_code == 200:
                print(f"Ollama connected ({self.model_name})")
            else:
                print(f"Ollama responded with {r.status_code}")
        except Exception as e:
            print(f"Ollama connection failed: {e}")

    def _ollama_chat(self, messages: list) -> str:
        """Send chat payload to Ollama and return clean text output."""
        safe_messages = []
        for m in messages:
            content = m.get("content", "")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            safe_messages.append({
                "role": m.get("role", "user"),
                "content": content
            })

        response = requests.post(
            f"{self.ollama_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": safe_messages,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens
                }
            },
            timeout=180,
        )

        if response.status_code != 200:
            raise Exception(f"Ollama error: {response.status_code} - {response.text}")

        data = response.json()
        msg = data.get("message", {})
        content = msg.get("content", "")

        if isinstance(content, dict):
            
            content = content.get("assistant") or content.get("text") or json.dumps(content, ensure_ascii=False)
        elif isinstance(content, (list, tuple)):
        
            content = " ".join(str(x) for x in content)

        try:
            
            if isinstance(content, str) and content.strip().startswith("{") and content.strip().endswith("}"):
                possible_json = json.loads(content)
                if isinstance(possible_json, dict) and "assistant" in possible_json:
                    content = possible_json["assistant"]
        except Exception:
            pass

        return str(content).strip()


    def _extract_action(self, text: str) -> Dict[str, Any]:
        """Extract JSON action {action: <tool>, args: {...}} from model output."""
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
            if "action" in data:
                return data
        except json.JSONDecodeError:
            pass
        return {}

    def _normalize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Fix mismatched arg names (e.g., query→name)."""
        if not args:
            return {}
        mapping = {"q": "name", "query": "name", "target": "name"}
        return {mapping.get(k, k): v for k, v in args.items()}

    def _run_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Safely execute a tool and return structured JSON output."""
        tool = next((t for t in tools if t["name"] == name), None)
        if not tool:
            return {"error": f"Unknown tool '{name}'"}
        try:
            args = self._normalize_args(args)
            print(f"Running tool: {name}({args})")
            result = tool["func"](**args)
            if isinstance(result, tuple):
                result = result[0]
            if hasattr(result, "to_dict"):
                result = result.to_dict(orient="records")
            if isinstance(result, str):
                result = {"output": result}
            return result
        except Exception as e:
            print(f"Tool {name} failed: {e}")
            return {"error": str(e)}

    def process_message(self, messages: List[Dict[str, Any]], user_input: str) -> tuple[List[Dict[str, Any]], str]:
        """
        Process a user message, decide whether to call a tool, execute it, and return updated chat.
        """
        messages.append({"role": "user", "content": user_input})
        api_messages = [{"role": "system", "content": self.system_prompt}] + messages

        # Step 1 — Ask Mistral what to do next
        try:
            reply = self._ollama_chat(api_messages)
        except Exception as e:
            return messages, f"Ollama error: {e}"

        messages.append({"role": "assistant", "content": reply})
        print(f"\nModel reply:\n{reply}\n")

        # Step 2 — Detect JSON action
        action = self._extract_action(reply)
        if not action or action.get("action") == "finish":
            return messages, reply

        tool_name = action.get("action")
        args = action.get("args", {})

        # Step 3 — Run the tool
        result = self._run_tool(tool_name, args)
        messages.append({"role": "tool", "name": tool_name, "content": json.dumps(result)[:2000]})

        # Step 4 — Ask Mistral to interpret results
        api_messages = [{"role": "system", "content": self.system_prompt}] + messages
        try:
            followup = self._ollama_chat(api_messages)
        except Exception as e:
            followup = f"Tool '{tool_name}' executed but summary failed: {e}"

        messages.append({"role": "assistant", "content": followup})
        return messages, followup
