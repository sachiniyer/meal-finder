import "../styles/globals.css";
import "github-markdown-css";
import "../styles/markdown-dark.css";
import type { AppProps } from "next/app";
import { useEffect } from "react";
import { LocationProvider } from "../context/LocationContext";
import { ChatProvider } from "../context/ChatContext";
import { TokenProvider } from "../context/TokenContext";

function MyApp({ Component, pageProps }: AppProps) {
  useEffect(() => {
    document.documentElement.classList.add("dark");
  }, []);

  return (
    <TokenProvider>
      <LocationProvider>
        <ChatProvider>
          <Component {...pageProps} />
        </ChatProvider>
      </LocationProvider>
    </TokenProvider>
  );
}

export default MyApp;
