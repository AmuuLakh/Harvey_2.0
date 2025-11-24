from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich import box
import textwrap
import os
import traceback

from harvey.agent import HarveyAgent

console = Console()

ASCII_ART = r"""
██╗  ██╗ █████╗ ██████╗ ██╗   ██╗███████╗██╗   ██╗
██║  ██║██╔══██╗██╔══██╗██║   ██║██╔════╝╚██╗ ██╔╝
███████║███████║██████╔╝██║   ██║█████╗   ╚████╔╝ 
██╔══██║██╔══██║██╔══██╗╚██╗ ██╔╝██╔══╝    ╚██╔╝  
██║  ██║██║  ██║██║  ██║ ╚████╔╝ ███████╗   ██║   
╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝   ╚═╝

            HARVEY Autonomous OSINT Agent
"""

WELCOME_TEXT = "Type messages normally. Commands start with '/'. Use /help to see your options."


def print_header():
    header = Panel(
        Text(ASCII_ART, style="bold cyan"),
        expand=True,
        border_style="cyan",
        box=box.ROUNDED
    )
    console.print(header)
    console.print(Text(WELCOME_TEXT, style="dim"))
    console.print()


def print_help():
    help_text = textwrap.dedent("""
    [bold cyan]Available Commands[/bold cyan]

    [yellow]/help[/yellow]            Show this help text
    [yellow]/history[/yellow]         Show conversation history
    [yellow]/clear[/yellow]           Clear the screen
    [yellow]/exit[/yellow] / [yellow]/quit[/yellow]   Exit Harvey

    Notes:
      - To trigger an investigation type find <your_target> or investigate <your_target>
    """)
    console.print(Panel(help_text, border_style="cyan", box=box.ROUNDED))


def format_pair(user_msg, harvey_msg, index=None):
    title = f"Message {index}" if index is not None else "Conversation Entry"
    body = (
        f"[bold yellow]You:[/bold yellow] {user_msg}\n"
        f"[bold green]Harvey:[/bold green] {harvey_msg}"
    )
    return Panel(body, title=title, border_style="magenta", box=box.ROUNDED)


def main():
    agent = HarveyAgent()
    messages = []

    print_header()

    try:
        while True:
            try:
                user_input = Prompt.ask("[bold yellow]You[/bold yellow]")
            except (KeyboardInterrupt, EOFError):
                console.print("[red]Exiting Harvey.[/red]")
                break

            if not user_input.strip():
                continue

            # --- Commands ---
            if user_input.startswith("/"):
                parts = user_input.split(maxsplit=1)
                cmd = parts[0].lower()

                if cmd in ("/exit", "/quit"):
                    console.print("[red]Goodbye.[/red]")
                    break

                if cmd == "/help":
                    print_help()
                    continue

                if cmd == "/history":
                    if not messages:
                        console.print("[dim]No history yet.[/dim]")
                        continue
                    for i in range(0, len(messages), 2):
                        panel = format_pair(
                            messages[i],
                            messages[i + 1] if i + 1 < len(messages) else "",
                            index=(i // 2) + 1
                        )
                        console.print(panel)
                    continue

                if cmd == "/clear":
                    os.system("cls" if os.name == "nt" else "clear")
                    print_header()
                    continue

                console.print("[red]Unknown command. Use /help.[/red]")
                continue

            # --- Normal Harvey message ---
            try:
                messages, response = agent.process_message(messages, user_input)
            except TypeError:
                # fallback
                resp = agent.process_message(user_input)
                response = resp if isinstance(resp, str) else str(resp)
                messages.append(user_input)
                messages.append(response)
            except Exception as e:
                console.print(f"[bold red]Agent error:[/bold red] {e}")
                console.print(traceback.format_exc())
                continue

            messages.append(user_input)
            messages.append(response)

            console.print(Panel(
                Text(response, style="green"),
                title="[cyan]Harvey[/cyan]",
                border_style="cyan",
                box=box.ROUNDED
            ))

    except Exception as e:
        console.print(f"[bold red]Fatal Error:[/bold red] {e}")
        console.print(traceback.format_exc())
