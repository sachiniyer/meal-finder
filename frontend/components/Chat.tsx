import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { useChat } from "../context/ChatContext";
import { useLocation } from "../context/LocationContext";
import { useToken } from "../context/TokenContext";

const backendUrl =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

interface Message {
  content: string;
  sender: "user" | "assistant" | "tool";
  id: string; // Used to identify and remove tool messages
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { currentChatId, setCurrentChatId } = useChat();
  const { location, isLoading: locationLoading } = useLocation();
  const { token, resetToken, socket } = useToken();

  useEffect(() => {
    if (!socket) return;

    // Handle existing messages when loading a chat
    const handleMessages = (data: {
      messages: Array<{ content: string; role: string }>;
    }) => {
      console.log("Received messages:", data.messages);
      const formatted = data.messages.map((msg) => ({
        content: msg.content,
        sender: (msg.role === "user" ? "user" : "assistant") as
          | "user"
          | "assistant"
          | "tool",
        id: Math.random().toString(),
      }));
      setMessages(formatted);
    };

    // Handle new message
    const handleMessage = (data: { content: string; chat_id?: string }) => {
      if (currentChatId === null && data.chat_id) {
        setCurrentChatId(data.chat_id);
      }
      setMessages((prev) =>
        prev
          .filter((m) => m.sender !== "tool")
          .concat({
            content: data.content,
            sender: "assistant",
            id: Date.now().toString(),
          }),
      );
    };

    // Handle tool call
    const handleToolCall = (data: { chat_id?: string; tool_data: any }) => {
      console.log("Tool call event:", data);
      setMessages((prev) => [
        ...prev,
        {
          content: `🧠 Thinking... ${data.tool_data}`,
          sender: "tool",
          id: Date.now().toString(),
        },
      ]);
    };

    // Handle errors
    const handleError = (err: { chat_id?: string; error: string }) => {
      console.error("Error from server:", err.error);
      setErrorMsg(err.error);
      if (err.chat_id) {
        setCurrentChatId(err.chat_id);
      }
    };

    // Attach events
    socket.on("messages", handleMessages);
    socket.on("message", handleMessage);
    socket.on("tool_call", handleToolCall);
    socket.on("error", handleError);

    // Clean up
    return () => {
      socket.off("messages", handleMessages);
      socket.off("message", handleMessage);
      socket.off("tool_call", handleToolCall);
      socket.off("error", handleError);
    };
  }, [socket, currentChatId, setCurrentChatId, resetToken]);

  useEffect(() => {
    if (currentChatId && socket) {
      console.log("Fetching messages for chat:", currentChatId);
      socket.emit("get_messages", { chat_id: currentChatId });
    } else {
      setMessages([]);
    }
  }, [currentChatId, socket]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!inputValue.trim() || !socket || !location) return;

    // Add user message to the chat immediately
    setMessages((prev) => [
      ...prev,
      {
        content: inputValue,
        sender: "user",
        id: Date.now().toString(),
      },
    ]);

    socket.emit("send_message", {
      chat_id: currentChatId,
      content: inputValue,
      location: location,
    });

    setInputValue("");
  };

  // Show loading state while getting location
  if (locationLoading) {
    return (
      <div className="flex flex-col h-screen items-center justify-center p-4">
        <div className="text-gray-300">Loading location...</div>
      </div>
    );
  }

  // Show error if no location is available
  if (!location) {
    return (
      <div className="flex flex-col h-screen items-center justify-center p-4">
        <div className="text-red-400">
          Unable to access location. Please enable location services and refresh
          the page.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen p-4">
      {errorMsg && (
        <div className="bg-red-700 p-2 mb-2 text-white rounded">
          Error: {errorMsg}
        </div>
      )}
      <div className="flex-1 overflow-y-auto space-y-4 min-h-0">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`p-4 rounded-lg max-w-[80%] ${
              msg.sender === "user"
                ? "ml-auto bg-blue-600 text-white"
                : msg.sender === "tool"
                ? "bg-yellow-900/50 text-yellow-100"
                : "bg-gray-800 text-white"
            } ${msg.sender === "user" ? "ml-auto" : "mr-auto"}`}
          >
            <ReactMarkdown
              className={`markdown-body prose prose-invert max-w-none ${
                msg.sender === "user"
                  ? "text-white"
                  : msg.sender === "tool"
                  ? "text-yellow-100 prose-code:text-yellow-200 prose-pre:bg-black/20"
                  : "text-white"
              } ${
                msg.sender !== "user" &&
                `
                  prose-headings:text-gray-100
                  prose-p:text-gray-100
                  prose-strong:text-white
                  prose-code:text-gray-200
                  prose-pre:bg-black/20
                  prose-pre:border
                  prose-pre:border-gray-700
                  prose-a:text-blue-400
                  prose-li:text-gray-100
                  prose-table:text-gray-100
                  prose-hr:border-gray-700
                `
              }`}
              components={{
                pre: ({ children }) => (
                  <pre className="rounded-md p-4 overflow-auto">{children}</pre>
                ),
                code: ({ children }) => (
                  <code className="bg-black/20 rounded px-1 py-0.5">
                    {children}
                  </code>
                ),
              }}
            >
              {msg.content}
            </ReactMarkdown>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="mt-4 flex shrink-0">
        <input
          className="flex-1 bg-gray-700 text-gray-100 px-4 py-3 rounded-lg mr-2 outline-none focus:ring-1 focus:ring-gray-500"
          type="text"
          placeholder="Type your message..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <button
          className="bg-gray-700 px-6 py-3 rounded-lg hover:bg-gray-600 transition-colors"
          onClick={handleSend}
        >
          Send
        </button>
      </div>
    </div>
  );
}
