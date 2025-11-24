"""Configuration module for Harvey OSINT package."""
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

console = Console()

def get_config_dir() -> Path:
    """Get or create the config directory for Harvey."""
    if sys.platform == "win32":
        config_dir = Path(os.environ.get("APPDATA", "~")) / "harvey"
    else:
        config_dir = Path.home() / ".config" / "harvey"
    
    config_dir = config_dir.expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def get_env_file_path() -> Path:
    """Get the path to the .env file."""
    return get_config_dir() / ".env"

def load_github_token() -> str:
    """Load GitHub token from config file or environment."""
    # First check environment variable
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return token
    
    # Then check config file
    env_file = get_env_file_path()
    if env_file.exists():
        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GITHUB_TOKEN="):
                        token = line.split("=", 1)[1].strip()
                        # Set it in environment for current session
                        os.environ["GITHUB_TOKEN"] = token
                        return token
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read config file: {e}[/yellow]")
    
    return ""

def save_github_token(token: str) -> bool:
    """Save GitHub token to config file."""
    try:
        env_file = get_env_file_path()
        
        # Read existing content
        existing_lines = []
        if env_file.exists():
            with open(env_file, "r") as f:
                existing_lines = [line for line in f if not line.strip().startswith("GITHUB_TOKEN=")]
        
        # Write back with new token
        with open(env_file, "w") as f:
            for line in existing_lines:
                f.write(line)
            f.write(f"GITHUB_TOKEN={token}\n")
        
        # Set permissions (Unix-like systems only)
        if sys.platform != "win32":
            os.chmod(env_file, 0o600)
        
        # Set in current environment
        os.environ["GITHUB_TOKEN"] = token
        
        return True
    except Exception as e:
        console.print(f"[red]Error saving token: {e}[/red]")
        return False

def setup_github_token() -> bool:
    """Interactive setup for GitHub token."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]Harvey OSINT Configuration[/bold cyan]\n\n"
        "Harvey uses the GitHub API to gather public profile information.\n"
        "While not strictly required, a GitHub token provides:\n"
        "  • Higher API rate limits (5000 vs 60 requests/hour)\n"
        "  • More reliable data collection\n"
        "  • Better results for intensive searches\n\n"
        "[dim]You can create a token at: https://github.com/settings/tokens[/dim]\n"
        "[dim]Required scopes: None (public read-only access)[/dim]",
        border_style="cyan"
    ))
    
    # Check if token already exists
    existing_token = load_github_token()
    if existing_token:
        console.print(f"\n[green]✓[/green] GitHub token is already configured")
        if not Confirm.ask("Do you want to update it?", default=False):
            return True
    
    # Ask if user wants to configure now
    if not Confirm.ask("\nWould you like to configure your GitHub token now?", default=True):
        console.print("\n[yellow]Skipping configuration.[/yellow]")
        console.print("You can configure it later by running: [bold]harvey-config[/bold]")
        return False
    
    # Get token from user
    console.print()
    token = Prompt.ask(
        "[cyan]Enter your GitHub Personal Access Token[/cyan]",
        password=True
    ).strip()
    
    if not token:
        console.print("[yellow]No token provided. Skipping configuration.[/yellow]")
        return False
    
    # Validate token format (basic check)
    if len(token) < 20:
        console.print("[red]Invalid token format. GitHub tokens are typically 40+ characters.[/red]")
        return False
    
    # Save token
    if save_github_token(token):
        console.print(f"\n[green]✓[/green] GitHub token saved successfully!")
        console.print(f"[dim]Config file: {get_env_file_path()}[/dim]")
        
        # Test the token
        console.print("\n[cyan]Testing token...[/cyan]")
        if test_github_token(token):
            console.print("[green]✓[/green] Token is valid and working!")
            return True
        else:
            console.print("[yellow]⚠[/yellow] Token saved but validation failed. Please check your token.")
            return False
    else:
        console.print("[red]✗[/red] Failed to save token")
        return False

def test_github_token(token: str) -> bool:
    """Test if GitHub token is valid."""
    try:
        import requests
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        return response.status_code == 200
    except Exception as e:
        console.print(f"[dim]Test error: {e}[/dim]")
        return False

def configure_token_cli():
    """CLI command for configuring token."""
    try:
        success = setup_github_token()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Configuration cancelled.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error during configuration: {e}[/red]")
        sys.exit(1)

def show_config_info():
    """Display current configuration information."""
    console.print(Panel.fit(
        "[bold cyan]Harvey Configuration Info[/bold cyan]",
        border_style="cyan"
    ))
    
    config_dir = get_config_dir()
    env_file = get_env_file_path()
    token = load_github_token()
    
    console.print(f"\n[cyan]Config Directory:[/cyan] {config_dir}")
    console.print(f"[cyan]Config File:[/cyan] {env_file}")
    console.print(f"[cyan]Token Status:[/cyan] {'✓ Configured' if token else '✗ Not configured'}")
    
    if token:
        console.print(f"[cyan]Token (masked):[/cyan] {token[:8]}...{token[-4:]}")

# Load token on module import
load_github_token()