import os
import sys
import time
import textwrap
from shutil import get_terminal_size
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from agent import HarveyAgent

ANSI_RESET = "\u001b[0m"
ANSI_BOLD = "\u001b[1m"
ANSI_DIM = "\u001b[2m"
ANSI_GREEN = "\u001b[32m"
ANSI_CYAN = "\u001b[36m"
ANSI_YELLOW = "\u001b[33m"
ANSI_MAGENTA = "\u001b[35m"

ASCII_ART = r"""
██╗  ██╗ █████╗ ██████╗ ██╗   ██╗███████╗██╗   ██╗
██║  ██║██╔══██╗██╔══██╗██║   ██║██╔════╝╚██╗ ██╔╝
███████║███████║██████╔╝██║   ██║█████╗   ╚████╔╝ 
██╔══██║██╔══██║██╔══██╗╚██╗ ██╔╝██╔══╝    ╚██╔╝  
██║  ██║██║  ██║██║  ██║ ╚████╔╝ ███████╗   ██║   
╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝   ╚═╝                                                  

                 HARVEY Autonomous OSINT Agent
"""

WELCOME_TEXT = "Type a message and press Enter. Commands start with '/'. Type /help for shortcuts."


def center(text: str) -> str:
    cols = get_terminal_size((80, 20)).columns
    return "\n".join(line.center(cols) for line in text.splitlines())


def print_header():
    console = Console()
    ascii_text = Text(ASCII_ART, style="bold cyan")
    console.print(Panel(ascii_text, expand=True, border_style="cyan"))
    console.print(Text(WELCOME_TEXT, style="dim"))
    console.print()


def print_help():
    help_text = textwrap.dedent(f"""
    Commands:
      /help            Show this help text
      /history         Show message history (your messages and Harvey's replies)
      /save <filename> Save the current conversation to a text file
      /clear           Clear the screen
      /exit or /quit   Exit the interface

    Notes:
      - Regular input is sent to HarveyAgent.process_message(messages, user_input)
      - The program expects an object `HarveyAgent` available from `from agent import HarveyAgent`.
    """)
    print(help_text)


def format_pair(user_msg: str, harvey_msg: str, index=None) -> str:
    prefix = f"[{index}] " if index is not None else ""
    return (
        ANSI_BOLD + f"{prefix}You: " + ANSI_RESET + f"{user_msg}\n"
        + ANSI_GREEN + "Harvey: " + ANSI_RESET + f"{harvey_msg}\n"
    )


def save_history(messages, filename):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("Harvey Conversation Log\n")
            f.write("Generated: " + time.asctime() + "\n\n")
            for i in range(0, len(messages), 2):
                user = messages[i] if i < len(messages) else ""
                harvey = messages[i + 1] if i + 1 < len(messages) else ""
                f.write("You: " + user + "\n")
                f.write("Harvey: " + harvey + "\n\n")
        print(ANSI_YELLOW + f"Saved conversation to {filename}" + ANSI_RESET)
    except Exception as e:
        print(ANSI_MAGENTA + "Failed to save: " + str(e) + ANSI_RESET)


def main():
    agent = HarveyAgent()
    messages = []

    print_header()

    try:
        while True:
            try:
                user_input = input(ANSI_BOLD + "You: " + ANSI_RESET)
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not user_input.strip():
                continue

            if user_input.startswith("/"):
                parts = user_input.strip().split(maxsplit=1)
                cmd = parts[0].lower()

                if cmd in ("/exit", "/quit"):
                    print("Goodbye.")
                    break
                if cmd == "/help":
                    print_help()
                    continue
                if cmd == "/history":
                    if not messages:
                        print(ANSI_DIM + "No history yet." + ANSI_RESET)
                        continue
                    for i in range(0, len(messages), 2):
                        user = messages[i] if i < len(messages) else ""
                        harvey = messages[i + 1] if i + 1 < len(messages) else ""
                        print(format_pair(user, harvey, index=(i//2)+1))
                    continue
                if cmd == "/clear":
                    os.system("cls" if os.name == "nt" else "clear")
                    print_header()
                    continue
                if cmd == "/save":
                    filename = parts[1] if len(parts) > 1 else "harvey_conversation.txt"
                    save_history(messages, filename)
                    continue

                print(ANSI_MAGENTA + "Unknown command. Type /help." + ANSI_RESET)
                continue

            # pass to agent
            try:
                messages, response = agent.process_message(messages, user_input)
            except TypeError:
                # if agent returns different contract, try the simple style
                resp = agent.process_message(user_input)
                response = resp if isinstance(resp, str) else str(resp)
                # append to messages in best-effort way
                messages.append(user_input)
                messages.append(response)
            except Exception as e:
                print(ANSI_MAGENTA + "Agent error: " + str(e) + ANSI_RESET)
                continue

            # display
            print(ANSI_GREEN + "Harvey: " + ANSI_RESET + response + "\n")

    except Exception as e:
        print(ANSI_MAGENTA + "Fatal error: " + str(e) + ANSI_RESET)


if __name__ == "__main__":
    main()
