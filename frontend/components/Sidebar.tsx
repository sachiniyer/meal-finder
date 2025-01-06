import React, { useEffect, useState, useRef } from "react";
import { useChat } from "../context/ChatContext";
import { useToken } from "../context/TokenContext";

interface Chat {
  chat_id: string;
  messages: [{ role: string; content: string }];
  created_at: number;
}

export default function Sidebar() {
  const [chats, setChats] = useState<Chat[]>([]);
  const initialLoadDone = useRef(false);
  const { currentChatId, setCurrentChatId } = useChat();
  const { token: _token, resetToken: _resetToken, socket } = useToken();

  useEffect(() => {
    if (!socket) return;

    // Listen for updates to the chat list
    const handleChats = (data: { chats: Chat[] }) => {
      const permanentChats = data.chats;
      if (!initialLoadDone.current && permanentChats.length > 0) {
        setCurrentChatId(permanentChats[0].chat_id);
      }
      const sorted = [...permanentChats].sort(
        (a, b) => b.created_at - a.created_at,
      );
      setChats(sorted);
      initialLoadDone.current = true;
    };

    socket.on("chats", handleChats);
    socket.emit("get_chats");

    return () => {
      socket.off("chats", handleChats);
    };
  }, [socket, currentChatId, setCurrentChatId]);

  const handleNewChat = () => {
    setCurrentChatId(null);
  };

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const handleSelectChat = (chatId: string) => {
    setCurrentChatId(chatId);
  };

  return (
    <div className="w-64 bg-gray-900 h-screen flex flex-col">
      <div className="p-4 border-b border-gray-800">
        <h1 className="text-xl font-bold text-white">Meal Finder</h1>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        {currentChatId === null && (
          <div className="w-full p-4 bg-gray-800 border-l-4 border-blue-500">
            <div className="text-sm text-gray-300">
              {formatDate(Date.now() / 1000)}
            </div>
            <div className="text-white truncate">New conversation...</div>
          </div>
        )}

        {chats.map((chat) => (
          <button
            key={chat.chat_id}
            onClick={() => handleSelectChat(chat.chat_id)}
            className={`w-full p-4 text-left hover:bg-gray-800 transition-colors ${
              currentChatId === chat.chat_id ? "bg-gray-800" : ""
            } ${currentChatId === null ? "opacity-50" : ""}`}
          >
            <div className="text-sm text-gray-300">
              {formatDate(chat.created_at)}
            </div>
            <div className="text-white truncate">
              {chat.messages[0].content.slice(0, 30)}...
            </div>
          </button>
        ))}
      </div>

      <div className="p-4 border-t border-gray-800 shrink-0">
        <button
          onClick={handleNewChat}
          disabled={currentChatId === null}
          className={`w-full p-3 rounded transition-colors flex items-center justify-center space-x-2
            ${
              currentChatId === null
                ? "bg-gray-600 text-gray-400 cursor-not-allowed"
                : "bg-gray-700 text-white hover:bg-gray-600"
            }`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
              clipRule="evenodd"
            />
          </svg>
          <span>New Search</span>
        </button>
      </div>
    </div>
  );
}
