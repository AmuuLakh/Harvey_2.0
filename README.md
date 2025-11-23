# Harvey OSINT

Harvey - Autonomous OSINT Reconnaissance Agent for LinkedIn and GitHub profiling.

Harvey is a powerful Open Source Intelligence (OSINT) tool that helps you gather public information about individuals from LinkedIn, GitHub, and other public sources. Perfect for security researchers, recruiters, journalists, and investigators.

## Features

- LinkedIn Profile Discovery - Find and scrape public LinkedIn profiles
- GitHub Analysis - Fetch GitHub profiles, repos, and activity
- Cross-Platform Linking - Automatically validates LinkedIn profiles using GitHub data
- Comprehensive Reports - Generate detailed reports in TXT and CSV formats
- Autonomous Operation - Smart agent-based investigation workflow
- Data Persistence - Save all findings for future reference

## Installation

### From PyPI (Recommended)

```bash
pip install harvey-osint (broken at the moment)
```

### From Source

```bash
git clone https://github.com/yourusername/harvey-osint.git
cd harvey-osint
pip install -e .
```

## Quick Start

### 1. Configure GitHub Token (Recommended)

Harvey works better with a GitHub Personal Access Token for higher rate limits:

```bash
harvey-config
```

Create a token at: https://github.com/settings/tokens (no special scopes needed)

### 2. Run Harvey

```bash
harvey
```

### 3. Start Investigating

```
You: investigate John Doe
Harvey: [Begins comprehensive OSINT investigation]

You: make report
Harvey: [Generates detailed report and saves to files]
```

## Usage Examples

### Interactive CLI

```bash
# Start Harvey
harvey

# Investigate someone
You: research Jane Smith

# Generate a report
You: make report

# Get help
You: /help
```

### Python API

```python
from harvey import HarveyAgent

# Initialize agent
agent = HarveyAgent()
messages = []

# Investigate a target
messages, response = agent.process_message(
    messages, 
    "investigate Satya Nadella"
)
print(response)

# Generate report
messages, report = agent.process_message(
    messages,
    "make report"
)
print(report)
```

## Configuration

Harvey stores configuration in:
- Linux/Mac: ~/.config/harvey/.env
- Windows: %APPDATA%\harvey\.env

You can manually edit this file or use `harvey-config` to configure.

## GitHub Token Setup

While Harvey can work without a GitHub token, having one provides:
- Higher API rate limits (5000 vs 60 requests/hour)
- More reliable data collection
- Better results for intensive searches

**Create a token:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. No special scopes needed - just read access
4. Copy the token and run `harvey-config`

## Commands

Interactive CLI commands:
- `/help` - Show help information
- `/history` - View conversation history
- `/clear` - Clear the screen
- `/exit` or `/quit` - Exit Harvey

## Output

Harvey generates two types of reports:

1. **Text Reports** ({name}_report_{timestamp}.txt)
   - Human-readable investigation summary
   - LinkedIn profiles found
   - GitHub profile information
   - Portfolio links
   - Validation status

2. **CSV Data** ({name}_data_{timestamp}.csv)
   - Structured data for analysis
   - Easy import into spreadsheets
   - Machine-readable format

Reports are saved in the `reports/` directory.

## Legal and Ethical Use

**Important**: Harvey is designed for **legitimate OSINT purposes only**:
- Security research and penetration testing (with permission)
- Recruitment and talent sourcing
- Journalism and investigative reporting
- Background checks (where legally permitted)
- **NOT for harassment, stalking, or illegal activities**

**Always:**
- Respect privacy and applicable laws
- Only gather publicly available information
- Use data ethically and responsibly
- Comply with LinkedIn's and GitHub's Terms of Service

## Data Sources

Harvey only collects **publicly available** information from:
- Public LinkedIn profiles
- GitHub public profiles and repositories
- Search engine results
- Public websites and portfolios

## Rate Limits and Best Practices

- Harvey implements polite delays between requests
- Respects robots.txt and rate limits
- Uses search engines ethically
- Handles CAPTCHAs and blocks gracefully

## Troubleshooting

### "No LinkedIn profiles found"
- LinkedIn may require login for some profiles
- Try different name variations
- Check if the person has a public profile

### "GitHub API rate limit exceeded"
- Configure a GitHub token with `harvey-config`
- Wait for rate limit reset (check headers)
- Use token for 5000 requests/hour instead of 60

### "CAPTCHA detected"
- Harvey will skip CAPTCHA-protected pages
- Results will use fallback methods
- Consider reducing request frequency

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Disclaimer

This tool is provided for educational and legitimate research purposes only. Users are responsible for ensuring their use complies with all applicable laws and regulations. The authors assume no liability for misuse.


---

Made with care by the OSINT community
