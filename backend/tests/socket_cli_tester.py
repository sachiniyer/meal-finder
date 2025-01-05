#!/usr/bin/env python3
import socketio
import argparse
import json
from datetime import datetime
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich import print as rprint
import asyncio

# Load environment variables from .env file
load_dotenv()

class SocketChatTester:
    def __init__(self, base_url, output_dir="test_outputs", location=None):
        self.base_url = base_url.rstrip("/")
        self.chat_id = None
        self.console = Console()
        self.output_dir = output_dir
        self.location = location or {"latitude": 43.000000, "longitude": -75.000000}
        self.api_token = os.getenv('API_TOKEN')
        
        if not self.api_token:
            raise ValueError("API_TOKEN environment variable is required")

        # Create Socket.IO client
        self.sio = socketio.Client()
        self.setup_socket_handlers()

        # Message queue for receiving responses
        self.response_queue = asyncio.Queue()

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Create a new log file for this session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(output_dir, f"socket_chat_test_{timestamp}.json")
        self.chat_history = []

    def setup_socket_handlers(self):
        """Setup Socket.IO event handlers"""

        @self.sio.on("connect")
        def on_connect():
            self.console.print("[green]Connected to server")

        @self.sio.on("disconnect")
        def on_disconnect():
            self.console.print("[red]Disconnected from server")

        @self.sio.on("message")
        def on_message(data: dict):
            self.console.print(
                Panel(
                    Markdown(data["content"]),
                    title="Assistant",
                    border_style="blue",
                )
            )
            # If server sent a chat_id, store it
            if "chat_id" in data and not self.chat_id:
                self.chat_id = data["chat_id"]
            # Record the interaction
            self._record_response(data)

        @self.sio.on("tool_call")
        def on_tool_call(data: dict):
            self.console.print(
                Panel(
                    f"Tool Call: {data.get('tool_data', {})}",
                    title="Tool Call",
                    border_style="yellow",
                )
            )
            # If server sent a chat_id, store it
            if "chat_id" in data and not self.chat_id:
                self.chat_id = data["chat_id"]

        @self.sio.on("error")
        def on_error(data: dict):
            self.console.print(f"[red]Error: {data.get('error', 'Unknown error')}")
            # If server sent a chat_id, store it
            if "chat_id" in data and not self.chat_id:
                self.chat_id = data["chat_id"]

        @self.sio.on("chats")
        def on_chats(data):
            self.console.print(
                Panel(
                    json.dumps(data["chats"], indent=2),
                    title="Available Chats",
                    border_style="green",
                )
            )

        @self.sio.on("messages")
        def on_messages(data: dict):
            self.console.print(
                Panel(
                    json.dumps(data["messages"], indent=2),
                    title="Chat Messages",
                    border_style="cyan",
                )
            )
            # If server sent a chat_id, store it
            if "chat_id" in data and not self.chat_id:
                self.chat_id = data["chat_id"]

    def connect(self):
        """Connect to the Socket.IO server"""
        try:
            url_with_query = f"{self.base_url}?token={self.api_token}"
            self.sio.connect(
                url_with_query,
                auth={'token': self.api_token}
            )
        except Exception as e:
            self.console.print(f"[red]Error connecting to server: {str(e)}")
            raise

    def disconnect(self):
        """Disconnect from the Socket.IO server"""
        if self.sio.connected:
            self.sio.disconnect()

    def send_message(self, message):
        """Send a message through Socket.IO"""
        try:
            self.sio.emit(
                "send_message",
                {
                    "content": message,
                    "chat_id": self.chat_id,
                    "location": self.location,
                },
            )

            # Record the interaction
            interaction = {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "chat_id": self.chat_id,
                "location": self.location,
            }
            self.chat_history.append(interaction)
            self._save_history()

        except Exception as e:
            self.console.print(f"[red]Error sending message: {str(e)}")

    def get_chat_history(self):
        """Request chat history for current chat"""
        try:
            self.sio.emit("get_messages", {"chat_id": self.chat_id})
        except Exception as e:
            self.console.print(f"[red]Error retrieving chat history: {str(e)}")

    def get_all_chats(self):
        """Request list of all chats"""
        try:
            self.sio.emit("get_chats")
        except Exception as e:
            self.console.print(f"[red]Error retrieving chats: {str(e)}")

    def _record_response(self, response):
        """Record a response in the chat history"""
        if self.chat_history:
            self.chat_history[-1]["response"] = response
            self._save_history()

    def _save_history(self):
        """Save the chat history to a JSON file"""
        with open(self.log_file, "w") as f:
            json.dump(self.chat_history, f, indent=2)

    def set_location(self, latitude: float, longitude: float):
        """Update the location for future requests"""
        self.location = {"latitude": float(latitude), "longitude": float(longitude)}
        self.console.print(f"[green]Location updated to: {self.location}")


def main():
    parser = argparse.ArgumentParser(description="Test the chat API via Socket.IO")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--output",
        default="test_outputs",
        help="Directory for output files (default: test_outputs)",
    )
    parser.add_argument(
        "--lat",
        type=float,
        default=43.000000,
        help="Initial latitude (default: 43.000000)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        default=-75.000000,
        help="Initial longitude (default: -75.000000)",
    )

    args = parser.parse_args()

    initial_location = {"latitude": args.lat, "longitude": args.lon}
    tester = SocketChatTester(args.url, args.output, location=initial_location)

    # Welcome message
    tester.console.print(
        Panel(
            "[bold green]Socket.IO Chat API Tester[/bold green]\n"
            "Type your messages and press Enter to send.\n"
            "Special commands:\n"
            "  'history' - see the current chat history\n"
            "  'chats' - list all available chats\n"
            "  'location lat lon' - update your location\n"
            "  'quit' or 'exit' - end the session",
            title="Welcome",
            border_style="green",
        )
    )

    try:
        # Connect to the server
        tester.connect()

        while True:
            try:
                # Get user input
                message = input("\n[You]> ")

                # Handle special commands
                if message.lower() in ["quit", "exit"]:
                    break
                elif message.lower() == "history":
                    tester.get_chat_history()
                    continue
                elif message.lower() == "chats":
                    tester.get_all_chats()
                    continue
                elif message.lower().startswith("location "):
                    try:
                        _, lat, lon = message.split()
                        tester.set_location(float(lat), float(lon))
                    except ValueError:
                        tester.console.print(
                            "[red]Invalid location format. Use: location <latitude> <longitude>"
                        )
                    continue
                elif not message.strip():
                    continue

                # Send message
                tester.send_message(message)

            except KeyboardInterrupt:
                break
            except Exception as e:
                tester.console.print(f"[red]Error: {str(e)}")
                continue

    finally:
        # Disconnect and cleanup
        tester.disconnect()
        tester.console.print(
            f"\n[green]Chat session ended. Log saved to: {tester.log_file}"
        )


if __name__ == "__main__":
    main()
