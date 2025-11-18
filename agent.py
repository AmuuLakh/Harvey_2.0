import json
import re
import requests
from typing import List, Dict, Any
from tools import tools
from utils import load_json, loads_prompt


class HarveyAgent:
    """
    Harvey — Autonomous OSINT Reconnaissance Agent.
    Simple rule-based system that doesn't require Ollama or GPU.
    """

    def __init__(self):
        self.TOOLS_SCHEMA = load_json("tschema.json")
        self.system_prompt = loads_prompt("sprompt.yaml")
        self.investigation_mode = False
        self.current_target = None
        self.investigation_data = {}  

    def _extract_name_from_input(self, user_input: str) -> str:
        """Extract a person's name from user input"""
        cleaned = re.sub(r'^(research|investigate|analyze|find info on|look up|search for|find|report on|make report on)\s+', '', user_input.lower())
        cleaned = cleaned.strip()
        if re.match(r'^[a-zA-Z\s]+$', cleaned) and len(cleaned.split()) >= 2:
            return cleaned.title()
        
        return cleaned.title()

    def _simple_ai_decision(self, user_input: str, conversation_history: List) -> Dict:
        """Simple rule-based decision making instead of Ollama"""
        user_input_lower = user_input.lower()
        
        report_triggers = ["make report", "generate report", "show report", "give me the report", "what did you find"]
        if any(trigger in user_input_lower for trigger in report_triggers) and self.investigation_data:
            return {"action": "generate_report", "args": {}}

        investigation_triggers = ["research", "investigate", "analyze", "find info", "look up", "search for", "find", "report on"]
        if (re.match(r'^[a-zA-Z]+\s+[a-zA-Z]+$', user_input.strip()) and 
            len(user_input.split()) >= 2):
            self.investigation_mode = True
            self.current_target = user_input.strip().title()
            return {"action": "build_professional_snapshot", "args": {"name": self.current_target}}

        if any(trigger in user_input_lower for trigger in investigation_triggers):
            self.investigation_mode = True
            extracted_name = self._extract_name_from_input(user_input)
            if extracted_name and len(extracted_name.split()) >= 2:
                self.current_target = extracted_name
                return {"action": "build_professional_snapshot", "args": {"name": self.current_target}}

        if self.investigation_mode and self.current_target:
            if "github" in user_input_lower:
                return {"action": "find_github_by_name", "args": {"name": self.current_target}}
            elif "linkedin" in user_input_lower:
                return {"action": "search_linkedin_footprints", "args": {"name": self.current_target}}
            elif "portfolio" in user_input_lower or "website" in user_input_lower:
                return {"action": "build_professional_snapshot", "args": {"name": self.current_target}}

        greeting_triggers = ["hello", "hi", "hey", "greetings"]
        if any(trigger in user_input_lower for trigger in greeting_triggers):
            return {"action": "finish"}

        if re.match(r'^[a-zA-Z]+\s+[a-zA-Z]+$', user_input.strip()) and len(user_input.split()) >= 2:
            self.investigation_mode = True
            self.current_target = user_input.strip().title()
            return {"action": "build_professional_snapshot", "args": {"name": self.current_target}}
        return {"action": "finish"}

    def _run_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Safely execute a tool and return structured JSON output."""
        if name == "generate_report":
            return self._generate_comprehensive_report()
            
        tool = next((t for t in tools if t["name"] == name), None)
        if not tool:
            return {"error": f"Unknown tool '{name}'"}
        try:
            print(f"Running tool: {name}({args})")
            result = tool["func"](**args)
            if name == "build_professional_snapshot" and isinstance(result, tuple):
                snapshot_data, df = result
                self.investigation_data = snapshot_data  
                return snapshot_data  
            elif name == "build_professional_snapshot":
                self.investigation_data = result

            elif name == "find_github_by_name":
                self.investigation_data['github_search'] = result
            elif name == "search_linkedin_footprints":
                self.investigation_data['linkedin_search'] = result
            
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

    def _generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate a comprehensive report from all gathered data"""
        if not self.investigation_data:
            return {"error": "No investigation data available. Please research someone first."}
        
        report = {
            "target": self.current_target,
            "timestamp": "Generated on demand",
            "summary": "Comprehensive OSINT Report",
            "data": self.investigation_data
        }
        return report

    def process_message(self, messages: List[Dict[str, Any]], user_input: str) -> tuple[List[Dict[str, Any]], str]:
        """
        Process a user message using simple rule-based system.
        """
        messages.append({"role": "user", "content": user_input})

        action = self._simple_ai_decision(user_input, messages)
        
        if not action or action.get("action") == "finish":
            if self.investigation_mode and self.current_target and self.investigation_data:
                response = f"I've completed the investigation on {self.current_target}. Say 'make report' to see the full findings, or ask about specific details like GitHub or LinkedIn."
            elif self.investigation_mode and self.current_target:
                response = f"I'm ready to investigate {self.current_target}. Say 'research {self.current_target}' to begin, or 'make report' if you already have data."
            else:
                response = "Hello! I'm Harvey, your OSINT assistant. I can help you research people using public data from LinkedIn, GitHub, and other sources. Just tell me who you'd like me to investigate!"
            messages.append({"role": "assistant", "content": response})
            return messages, response

        tool_name = action.get("action")
        args = action.get("args", {})

        result = self._run_tool(tool_name, args)

        if tool_name == "build_professional_snapshot":
            response = self._format_snapshot_response(result)
        elif tool_name == "search_linkedin_footprints":
            response = self._format_linkedin_response(result)
        elif tool_name == "find_github_by_name":
            response = self._format_github_response(result)
        elif tool_name == "generate_report":
            response = self._format_report_response(result)
        else:
            response = f"Action completed. Result: {json.dumps(result, indent=2)[:500]}"

        messages.append({"role": "assistant", "content": response})
        return messages, response

    def _format_snapshot_response(self, result: Dict) -> str:
        """Format a professional snapshot into a readable report"""
        if "error" in result:
            return f"Investigation failed: {result['error']}"
        
        response = f"## Investigation Started: {self.current_target}\n\n"

        linkedin_profiles = result.get("linkedin_profiles_found", [])
        if linkedin_profiles:
            response += f"**LinkedIn Profiles Found:** {len(linkedin_profiles)}\n"
            for profile in linkedin_profiles[:3]:
                response += f"- {profile}\n"
            if result.get("validation_status") == "github_validated":
                response += f"\n**LinkedIn Validated via GitHub**\n"
        else:
            response += "**LinkedIn:** No public profiles found\n"
 
        github_data = result.get("github", {})
        if github_data and not github_data.get("error"):
            response += f"\n** GitHub:** {github_data.get('name', 'Unknown')} (@{github_data.get('github_username')})\n"
            response += f"Bio: {github_data.get('bio', 'Not provided')}\n"
            response += f"Public Repos: {github_data.get('public_repos', 0)}\n"

            if github_data.get("linkedin_from_github"):
                response += f"LinkedIn in GitHub: {github_data['linkedin_from_github']}\n"
                
            if github_data.get('top_repos'):
                response += f"Top Repos: {len(github_data['top_repos'])} repositories\n"
        elif github_data and github_data.get("error"):
            response += f"\n**GitHub:** {github_data.get('error')}\n"
        else:
            response += "\n**GitHub:** No profile found\n"

        portfolio = result.get("portfolio")
        if portfolio:
            response += f"\n**Portfolio/Website:** {portfolio}\n"

        linkedin_raw = result.get("linkedin_raw", [])
        if linkedin_raw and isinstance(linkedin_raw, list):
            for profile in linkedin_raw:
                if isinstance(profile, dict) and profile.get('full_name'):
                    response += f"\n**Profile Data:** {profile.get('full_name')}"
                    if profile.get('title'):
                        response += f" - {profile.get('title')}"
        
        response += f"\n\n**Data gathered and saved.** Say 'make report' to see the complete report!"
        return response

    def _format_linkedin_response(self, result: List) -> str:
        """Format LinkedIn search results"""
        if not result:
            return f"No LinkedIn profiles found for {self.current_target}."
        
        response = f"Found {len(result)} potential LinkedIn profiles for {self.current_target}:\n"
        for url in result[:3]:
            response += f"- {url}\n"
        return response

    def _format_github_response(self, result: Dict) -> str:
        """Format GitHub search results"""
        if not result or result.get("error"):
            return f"No GitHub profile found for {self.current_target}."
        
        if isinstance(result, str):
            return f"Found GitHub username: {result}"
        
        return f"Found GitHub user: {result.get('github_username', 'Unknown')} - {result.get('name', 'No name provided')}"

    def _format_report_response(self, result: Dict) -> str:
        """Format the comprehensive report"""
        if "error" in result:
            return result["error"]
        
        data = result.get("data", {})
        response = f"#COMPREHENSIVE OSINT REPORT\n"
        response += f"**Target:** {self.current_target}\n"
        response += f"**Generated:** {result.get('timestamp', 'Now')}\n\n"
        
        linkedin_profiles = data.get("linkedin_profiles_found", [])
        response += f"##LinkedIn Findings\n"
        response += f"Profiles Found: {len(linkedin_profiles)}\n"
        for i, profile in enumerate(linkedin_profiles[:5], 1):
            response += f"{i}. {profile}\n"
        
        if data.get("validation_status") == "github_validated":
            response += f"\n**LINKEDIN VALIDATED VIA GITHUB**\n"
            response += f"Using authoritative LinkedIn from GitHub profile\n"
        
        github_data = data.get("github", {})
        response += f"\n## GitHub Findings\n"
        if github_data and not github_data.get("error"):
            response += f"Username: {github_data.get('github_username')}\n"
            response += f"Name: {github_data.get('name', 'Not provided')}\n"
            response += f"Bio: {github_data.get('bio', 'Not provided')}\n"
            response += f"Location: {github_data.get('location', 'Not provided')}\n"
            response += f"Public Repositories: {github_data.get('public_repos', 0)}\n"
            response += f"Followers: {github_data.get('followers', 0)}\n"
            response += f"Following: {github_data.get('following', 0)}\n"
            
            if github_data.get("linkedin_from_github"):
                response += f"LinkedIn in GitHub Bio: {github_data['linkedin_from_github']}\n"
        else:
            response += "No GitHub profile found\n"
        
        # Portfolio Section
        portfolio = data.get("portfolio")
        response += f"\n## Portfolio/Website\n"
        if portfolio:
            response += f"Found: {portfolio}\n"
        else:
            response += "No portfolio website found\n"
        
        # Profile Data Section
        linkedin_raw = data.get("linkedin_raw", [])
        if linkedin_raw:
            response += f"\n## Profile Details\n"
            for profile in linkedin_raw:
                if isinstance(profile, dict):
                    if profile.get('full_name'):
                        response += f"**Name:** {profile.get('full_name')}\n"
                    if profile.get('title'):
                        response += f"**Title:** {profile.get('title')}\n"
                    if profile.get('job_title'):
                        response += f"**Job Title:** {profile.get('job_title')}\n"
                    if profile.get('talks_about'):
                        response += f"**About:** {profile.get('talks_about')}\n"
                    response += "---\n"
        
        response += f"\n## Summary\n"
        response += f"Total Data Sources: {len(linkedin_profiles) + (1 if github_data else 0)}\n"
        response += f"Confidence Level: {'High' if linkedin_profiles or github_data else 'Low'}\n"
        response += f"Recommendation: {'Further investigation recommended' if linkedin_profiles or github_data else 'Limited public data available'}\n"
        
        response += f"\n*Report generated from public sources only.*"
        return response