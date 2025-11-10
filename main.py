from agent import HarveyAgent

if __name__ == "__main__":
    agent = HarveyAgent()
    messages = []
    print("=== Harvey Autonomous OSINT Agent ===\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ("exit", "quit"):
            break
        messages, response = agent.process_message(messages, user_input)
        print(f"Harvey: {response}\n")
