import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { useChat } from "../context/ChatContext";
import { useLocation } from "../context/LocationContext";
import { useToken } from "../context/TokenContext";

interface Message {
  content: string;
  sender: "user" | "assistant" | "tool";
  id: string;
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [quickStartClicked, setQuickStartClicked] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { currentChatId, setCurrentChatId } = useChat();
  const { location, isLoading: locationLoading } = useLocation();
  const { token: _, resetToken, socket } = useToken();
  const [isSharing, setIsSharing] = useState(false);
  const [showCopied, setShowCopied] = useState(false);

  const quickStartOptions = [
    "Find some bagels near me",
    "Can you get the reviews for honeyhole in capitol hill seattle",
    "What are the reviews for Ramen Danbo in West Village NYC",
    "Are there vegan options at Mr. Charlie's in San Francisco",
  ];

  const handleQuickStart = (message: string) => {
    if (socket && location) {
      setQuickStartClicked(true);
      setMessages((prev) => [
        ...prev,
        {
          content: message,
          sender: "user",
          id: Date.now().toString(),
        },
      ]);

      socket.emit("send_message", {
        chat_id: currentChatId,
        content: message,
        location: location,
      });
    }
  };

  useEffect(() => {
    if (!socket) return;

    const handleMessages = (data: {
      messages: Array<{ content: string; role: string }>;
    }) => {
      console.log("Received messages:", data.messages);
      const formatted = data.messages
        .filter((msg) => msg.role !== "tool")
        .map((msg) => ({
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
        setQuickStartClicked(false);
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

  const handleShare = async () => {
    if (!currentChatId) return;

    const shareUrl = `${window.location.origin}/chat/${currentChatId}`;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setIsSharing(true);
      setShowCopied(true);
      setTimeout(() => setIsSharing(false), 1000);
      setTimeout(() => setShowCopied(false), 1000);
    } catch (err) {
      console.error("Failed to copy link:", err);
    }
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
            className={`p-4 rounded-lg max-w-[80%] animate-fade-in ${
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
      {currentChatId === null && !quickStartClicked && (
        <div className="grid grid-cols-4 gap-2 mb-4 animate-fade-in">
          {quickStartOptions.map((option, index) => (
            <button
              key={index}
              onClick={() => handleQuickStart(option)}
              className="text-left p-3 bg-gray-700 hover:bg-gray-600 rounded-lg text-gray-100 transition-colors text-sm"
            >
              {option}
            </button>
          ))}
        </div>
      )}
      <div className="mt-4 flex shrink-0 gap-2">
        <input
          className="flex-1 bg-gray-700 text-gray-100 px-4 py-3 rounded-lg outline-none focus:ring-1 focus:ring-gray-500"
          type="text"
          placeholder={
            currentChatId === null
              ? "What do you want to eat today?"
              : "Ask a follow up..."
          }
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
        {currentChatId && (
          <div className="relative">
            <button
              onClick={handleShare}
              className={`bg-gray-700 px-4 py-3 rounded-lg hover:bg-gray-600 transition-colors flex items-center
                ${isSharing ? "animate-share-click" : ""}`}
              title="Share chat link"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path d="M15 8a3 3 0 10-2.977-2.63l-4.94 2.47a3 3 0 100 4.319l4.94 2.47a3 3 0 10.895-1.789l-4.94-2.47a3.027 3.027 0 000-.74l4.94-2.47C13.456 7.68 14.19 8 15 8z" />
              </svg>
            </button>
            {showCopied && (
              <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-gray-800 text-white text-sm rounded animate-fade-in">
                Copied!
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
