import React, { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { io, Socket } from "socket.io-client";
import { getCookie, setCookie, deleteCookie } from "../utils/cookies";

interface TokenContextType {
  token: string | null;
  setToken: (token: string | null) => void;
  resetToken: () => void;
  socket: Socket | null;
}

const TokenContext = createContext<TokenContextType>({
  token: null,
  setToken: () => {},
  resetToken: () => {},
  socket: null,
});

export function TokenProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [socket, setSocket] = useState<Socket | null>(null);

  const resetToken = () => {
    if (socket) {
      socket.disconnect();
    }
    deleteCookie("apiToken");
    setSocket(null);
    setToken(null);
  };

  useEffect(() => {
    // Load token from cookie or prompt
    if (!token) {
      const cookieToken = getCookie("apiToken");
      if (cookieToken) {
        setToken(cookieToken);
      } else {
        const userToken = window.prompt("Please enter your API token:");
        if (userToken) {
          setToken(userToken);
          setCookie("apiToken", userToken);
        } else {
          setToken(null);
        }
      }
    }
  }, [token]);

  // Create socket once the token is set
  useEffect(() => {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

    if (token && !socket) {
      try {
        const newSocket = io(backendUrl, { 
          auth: { token },
          transports: ['polling'],
          reconnection: false,
          query: { token }
        });

        newSocket.on('connect', () => {
          console.log('Socket connected successfully');
          setSocket(newSocket);
        });

        newSocket.on('connect_error', (error) => {
          console.error('Socket connection error:', error);
          console.error("Connection failed, requesting new token");
          newSocket.disconnect();
          setSocket(null);
          resetToken();
        });

        newSocket.on('disconnect', (reason) => {
          console.log('Socket disconnected:', reason);
          setSocket(null);
          if (reason === 'io server disconnect') {
            resetToken();
          }
        });

      } catch (error) {
        console.error('Socket creation error:', error);
        setSocket(null);
        resetToken();
      }
    }

    return () => {
      if (socket) {
        socket.disconnect();
        setSocket(null);
      }
    };
  }, [token, resetToken]);

  // Don’t load children until token and socket are ready
  if (!token || !socket) {
    return <div style={{ color: "white", textAlign: "center", marginTop: 40 }}>Loading...</div>;
  }

  return (
    <TokenContext.Provider value={{ token, setToken, resetToken, socket }}>
      {children}
    </TokenContext.Provider>
  );
}

export function useToken() {
  return useContext(TokenContext);
} 