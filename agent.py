import json
import re
import requests
import csv
import os
from datetime import datetime
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
        self.investigation_data = {}  # Store all gathered data
        self.reports_dir = "reports"  # Directory to save reports
        
        # Create reports directory if it doesn't exist
        os.makedirs(self.reports_dir, exist_ok=True)

    def _extract_name_from_input(self, user_input: str) -> str:
        """Extract a person's name from user input"""
        # Remove common prefixes and clean the input
        cleaned = re.sub(r'^(research|investigate|analyze|find info on|look up|search for|find|report on|make report on)\s+', '', user_input.lower())
        cleaned = cleaned.strip()
        
        # If it's just a name (like "Amisha Lakhani"), return it directly
        if re.match(r'^[a-zA-Z\s]+$', cleaned) and len(cleaned.split()) >= 2:
            return cleaned.title()
        
        return cleaned.title()

    def _simple_ai_decision(self, user_input: str, conversation_history: List) -> Dict:
        """Simple rule-based decision making instead of Ollama"""
        user_input_lower = user_input.lower()
        
        # Check for report requests
        report_triggers = ["make report", "generate report", "show report", "give me the report", "what did you find"]
        if any(trigger in user_input_lower for trigger in report_triggers) and self.investigation_data:
            return {"action": "generate_report", "args": {}}
        
        # Check if user wants to start investigation or provided a name
        investigation_triggers = ["research", "investigate", "analyze", "find info", "look up", "search for", "find", "report on"]
        
        # If it's a clear name (2+ words, no special chars), treat as investigation
        if (re.match(r'^[a-zA-Z]+\s+[a-zA-Z]+$', user_input.strip()) and 
            len(user_input.split()) >= 2):
            self.investigation_mode = True
            self.current_target = user_input.strip().title()
            return {"action": "build_professional_snapshot", "args": {"name": self.current_target}}
        
        # Check for investigation triggers
        if any(trigger in user_input_lower for trigger in investigation_triggers):
            self.investigation_mode = True
            extracted_name = self._extract_name_from_input(user_input)
            if extracted_name and len(extracted_name.split()) >= 2:
                self.current_target = extracted_name
                return {"action": "build_professional_snapshot", "args": {"name": self.current_target}}
        
        # If we're already in investigation mode and user provides more specific requests
        if self.investigation_mode and self.current_target:
            if "github" in user_input_lower:
                return {"action": "find_github_by_name", "args": {"name": self.current_target}}
            elif "linkedin" in user_input_lower:
                return {"action": "search_linkedin_footprints", "args": {"name": self.current_target}}
            elif "portfolio" in user_input_lower or "website" in user_input_lower:
                return {"action": "build_professional_snapshot", "args": {"name": self.current_target}}
        
        # Greeting responses
        greeting_triggers = ["hello", "hi", "hey", "greetings"]
        if any(trigger in user_input_lower for trigger in greeting_triggers):
            return {"action": "finish"}
        
        # If user just says a name without trigger words, investigate it
        if re.match(r'^[a-zA-Z]+\s+[a-zA-Z]+$', user_input.strip()) and len(user_input.split()) >= 2:
            self.investigation_mode = True
            self.current_target = user_input.strip().title()
            return {"action": "build_professional_snapshot", "args": {"name": self.current_target}}
            
        # Default response for unknown queries
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
            
            # Handle tuple return from build_professional_snapshot
            if name == "build_professional_snapshot" and isinstance(result, tuple):
                snapshot_data, df = result
                self.investigation_data = snapshot_data  # Store the dict part
                return snapshot_data  # Return only the dict for processing
            elif name == "build_professional_snapshot":
                self.investigation_data = result
            
            # Store other tool results
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

    def _save_report_to_files(self, report_data: Dict, formatted_report: str) -> str:
        """Save report to both TXT and CSV files, return file paths"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\s-]', '', self.current_target).replace(' ', '_')
        
        # TXT file
        txt_filename = f"{safe_name}_report_{timestamp}.txt"
        txt_path = os.path.join(self.reports_dir, txt_filename)
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(formatted_report)
        
        # CSV file
        csv_filename = f"{safe_name}_data_{timestamp}.csv"
        csv_path = os.path.join(self.reports_dir, csv_filename)
        
        self._save_structured_data_to_csv(report_data, csv_path)
        
        return f"📁 Reports saved:\n- TXT: {txt_path}\n- CSV: {csv_path}"

    def _save_structured_data_to_csv(self, report_data: Dict, csv_path: str):
        """Save structured data to CSV format"""
        data = report_data.get("data", {})
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Basic Info
            writer.writerow(["OSINT REPORT - STRUCTURED DATA"])
            writer.writerow(["Target", report_data.get("target", "Unknown")])
            writer.writerow(["Generated", report_data.get("timestamp", "Unknown")])
            writer.writerow([])
            
            # LinkedIn Profiles
            writer.writerow(["LINKEDIN PROFILES"])
            linkedin_profiles = data.get("linkedin_profiles_found", [])
            if linkedin_profiles:
                writer.writerow(["URL", "Validation Status"])
                for profile in linkedin_profiles:
                    validation_status = "GitHub Validated" if data.get("validation_status") == "github_validated" and profile == data.get("linkedin_validated") else "Search Based"
                    writer.writerow([profile, validation_status])
            else:
                writer.writerow(["No LinkedIn profiles found"])
            writer.writerow([])
            
            # GitHub Data
            writer.writerow(["GITHUB DATA"])
            github_data = data.get("github", {})
            if github_data and not github_data.get("error"):
                writer.writerow(["Username", github_data.get("github_username", "")])
                writer.writerow(["Name", github_data.get("name", "")])
                writer.writerow(["Bio", github_data.get("bio", "")])
                writer.writerow(["Location", github_data.get("location", "")])
                writer.writerow(["Public Repos", github_data.get("public_repos", "")])
                writer.writerow(["Followers", github_data.get("followers", "")])
                writer.writerow(["Following", github_data.get("following", "")])
                writer.writerow(["LinkedIn from GitHub", github_data.get("linkedin_from_github", "")])
                writer.writerow(["Profile URL", github_data.get("profile_url", "")])
            else:
                writer.writerow(["No GitHub data available"])
            writer.writerow([])
            
            # Portfolio
            writer.writerow(["PORTFOLIO/WEBSITE"])
            portfolio = data.get("portfolio", "Not found")
            writer.writerow([portfolio])
            writer.writerow([])
            
            # LinkedIn Profile Details
            writer.writerow(["LINKEDIN PROFILE DETAILS"])
            linkedin_raw = data.get("linkedin_raw", [])
            if linkedin_raw:
                writer.writerow(["Full Name", "Title", "Job Title", "About", "Profile URL"])
                for profile in linkedin_raw:
                    if isinstance(profile, dict):
                        writer.writerow([
                            profile.get("full_name", ""),
                            profile.get("title", ""),
                            profile.get("job_title", ""),
                            profile.get("talks_about", ""),
                            profile.get("profile_url", "")
                        ])
            else:
                writer.writerow(["No LinkedIn profile details available"])
            writer.writerow([])
            
            # Summary
            writer.writerow(["SUMMARY"])
            linkedin_count = len(linkedin_profiles)
            has_github = 1 if github_data and not github_data.get("error") else 0
            writer.writerow(["Total Data Sources", linkedin_count + has_github])
            writer.writerow(["Confidence Level", "High" if linkedin_count > 0 or has_github > 0 else "Low"])
            writer.writerow(["LinkedIn Validation", data.get("validation_status", "Not validated")])

    def _generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate a comprehensive report from all gathered data"""
        if not self.investigation_data:
            return {"error": "No investigation data available. Please research someone first."}
        
        report = {
            "target": self.current_target,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": "Comprehensive OSINT Report",
            "data": self.investigation_data
        }
        return report

    def process_message(self, messages: List[Dict[str, Any]], user_input: str) -> tuple[List[Dict[str, Any]], str]:
        """
        Process a user message using simple rule-based system.
        """
        messages.append({"role": "user", "content": user_input})

        # Step 1 — Decide what to do
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

        # Step 2 — Run the tool
        result = self._run_tool(tool_name, args)
        
        # Step 3 — Format response based on tool results
        if tool_name == "build_professional_snapshot":
            response = self._format_snapshot_response(result)
        elif tool_name == "search_linkedin_footprints":
            response = self._format_linkedin_response(result)
        elif tool_name == "find_github_by_name":
            response = self._format_github_response(result)
        elif tool_name == "generate_report":
            formatted_report = self._format_report_response(result)
            # Save to files and add file info to response
            if "error" not in result:
                file_info = self._save_report_to_files(result, formatted_report)
                response = f"{formatted_report}\n\n{file_info}"
            else:
                response = formatted_report
        else:
            response = f"Action completed. Result: {json.dumps(result, indent=2)[:500]}"

        messages.append({"role": "assistant", "content": response})
        return messages, response

    def _format_snapshot_response(self, result: Dict) -> str:
        """Format a professional snapshot into a readable report"""
        if "error" in result:
            return f"Investigation failed: {result['error']}"
        
        response = f"## 🔍 Investigation Started: {self.current_target}\n\n"
        
        # LinkedIn results
        linkedin_profiles = result.get("linkedin_profiles_found", [])
        if linkedin_profiles:
            response += f"**📊 LinkedIn Profiles Found:** {len(linkedin_profiles)}\n"
            for profile in linkedin_profiles[:3]:
                response += f"- {profile}\n"
            
            # Show validation status
            if result.get("validation_status") == "github_validated":
                response += f"\n✅ **LinkedIn Validated via GitHub**\n"
        else:
            response += "**📊 LinkedIn:** No public profiles found\n"
        
        # GitHub results
        github_data = result.get("github", {})
        if github_data and not github_data.get("error"):
            response += f"\n**💻 GitHub:** {github_data.get('name', 'Unknown')} (@{github_data.get('github_username')})\n"
            response += f"Bio: {github_data.get('bio', 'Not provided')}\n"
            response += f"Public Repos: {github_data.get('public_repos', 0)}\n"
            
            # Show LinkedIn from GitHub if found
            if github_data.get("linkedin_from_github"):
                response += f"LinkedIn in GitHub: {github_data['linkedin_from_github']}\n"
                
            if github_data.get('top_repos'):
                response += f"Top Repos: {len(github_data['top_repos'])} repositories\n"
        elif github_data and github_data.get("error"):
            response += f"\n**💻 GitHub:** {github_data.get('error')}\n"
        else:
            response += "\n**💻 GitHub:** No profile found\n"
        
        # Portfolio
        portfolio = result.get("portfolio")
        if portfolio:
            response += f"\n**🌐 Portfolio/Website:** {portfolio}\n"
        
        # LinkedIn raw data
        linkedin_raw = result.get("linkedin_raw", [])
        if linkedin_raw and isinstance(linkedin_raw, list):
            for profile in linkedin_raw:
                if isinstance(profile, dict) and profile.get('full_name'):
                    response += f"\n**👤 Profile Data:** {profile.get('full_name')}"
                    if profile.get('title'):
                        response += f" - {profile.get('title')}"
        
        response += f"\n\n**💾 Data gathered and saved.** Say 'make report' to see the complete report and save files!"
        return response

    def _format_linkedin_response(self, result: List) -> str:
        """Format LinkedIn search results"""
        if not result:
            return f"No LinkedIn profiles found for {self.current_target}."
        
        response = f"🔍 Found {len(result)} potential LinkedIn profiles for {self.current_target}:\n"
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
        response = f"# 📊 COMPREHENSIVE OSINT REPORT\n"
        response += f"**Target:** {self.current_target}\n"
        response += f"**Generated:** {result.get('timestamp', 'Now')}\n\n"
        
        # LinkedIn Section
        linkedin_profiles = data.get("linkedin_profiles_found", [])
        response += f"## 🔗 LinkedIn Findings\n"
        response += f"Profiles Found: {len(linkedin_profiles)}\n"
        for i, profile in enumerate(linkedin_profiles[:5], 1):
            response += f"{i}. {profile}\n"
        
        # Show validation status
        if data.get("validation_status") == "github_validated":
            response += f"\n✅ **LINKEDIN VALIDATED VIA GITHUB**\n"
            response += f"Using authoritative LinkedIn from GitHub profile\n"
        
        # GitHub Section
        github_data = data.get("github", {})
        response += f"\n## 💻 GitHub Findings\n"
        if github_data and not github_data.get("error"):
            response += f"Username: {github_data.get('github_username')}\n"
            response += f"Name: {github_data.get('name', 'Not provided')}\n"
            response += f"Bio: {github_data.get('bio', 'Not provided')}\n"
            response += f"Location: {github_data.get('location', 'Not provided')}\n"
            response += f"Public Repositories: {github_data.get('public_repos', 0)}\n"
            response += f"Followers: {github_data.get('followers', 0)}\n"
            response += f"Following: {github_data.get('following', 0)}\n"
            
            # Show LinkedIn from GitHub
            if github_data.get("linkedin_from_github"):
                response += f"LinkedIn in GitHub Bio: {github_data['linkedin_from_github']}\n"
        else:
            response += "No GitHub profile found\n"
        
        # Portfolio Section
        portfolio = data.get("portfolio")
        response += f"\n## 🌐 Portfolio/Website\n"
        if portfolio:
            response += f"Found: {portfolio}\n"
        else:
            response += "No portfolio website found\n"
        
        # Profile Data Section
        linkedin_raw = data.get("linkedin_raw", [])
        if linkedin_raw:
            response += f"\n## 👤 Profile Details\n"
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
        
        response += f"\n## 📈 Summary\n"
        response += f"Total Data Sources: {len(linkedin_profiles) + (1 if github_data else 0)}\n"
        response += f"Confidence Level: {'High' if linkedin_profiles or github_data else 'Low'}\n"
        response += f"Recommendation: {'Further investigation recommended' if linkedin_profiles or github_data else 'Limited public data available'}\n"
        
        response += f"\n*Report generated from public sources only.*"
        return response