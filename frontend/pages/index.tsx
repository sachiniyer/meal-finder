import Sidebar from "../components/Sidebar";
import Chat from "../components/Chat";
import { ChatProvider } from "../context/ChatContext";

console.log('Backend URL:', process.env.NEXT_PUBLIC_BACKEND_URL);

export default function Home() {
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
