import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { useChat } from '../context/ChatContext';
import Sidebar from "../components/Sidebar";
import Chat from "../components/Chat";
import { ChatProvider } from "../context/ChatContext";

console.log('Backend URL:', process.env.NEXT_PUBLIC_BACKEND_URL);

export default function Home() {
  const router = useRouter();
  const { chatId } = router.query;
  const { setCurrentChatId } = useChat();

  useEffect(() => {
    if (chatId && typeof chatId === 'string') {
      setCurrentChatId(chatId);
      // Update URL without reload, removing the query parameter
      router.replace('/', undefined, { shallow: true });
    }
  }, [chatId, setCurrentChatId, router]);

  return (
    <ChatProvider>
      <div className="flex min-h-screen bg-gray-900 text-gray-200">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Chat />
        </div>
      </div>
    </ChatProvider>
  );
}
