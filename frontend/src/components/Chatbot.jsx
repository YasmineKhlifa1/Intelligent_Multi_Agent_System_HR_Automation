import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import "./Chatbot.css";

const Chatbot = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const ws = useRef(null);
  const messagesEndRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const userId = localStorage.getItem("userId");
  const token = localStorage.getItem("token");

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!userId || !token) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Please log in to use the chatbot." }
      ]);
      return;
    }

    const connectWebSocket = () => {
      const wsUrl = `ws://localhost:8003/ws/chat/${userId}?token=${encodeURIComponent(token)}`;
      ws.current = new WebSocket(wsUrl);
      console.log("Attempting to connect to:", wsUrl);

      ws.current.onopen = () => {
        console.log("WebSocket connection established");
        setIsReconnecting(false);
        reconnectAttempts.current = 0;
      };

      ws.current.onmessage = (event) => {
        console.log("Message received:", event.data);
        const data = JSON.parse(event.data);
        if (data.error) {
          setMessages((prev) => [...prev, { role: "assistant", content: data.error }]);
        } else {
          setMessages((prev) => [...prev, { role: data.role, content: data.content }]);
        }
        setIsLoading(false);
      };

      ws.current.onclose = (event) => {
        console.log("WebSocket connection closed:", event.code, event.reason);
        setIsReconnecting(true);
        setIsLoading(false);
        if (event.code === 4001 || event.code === 4003) {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `Authentication error: ${event.reason}. Please log in again.` }
          ]);
          setIsReconnecting(false);
        } else {
          attemptReconnect();
        }
      };

      ws.current.onerror = (error) => {
        console.error("WebSocket error:", error);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Connection error. Please check your network or try again later." }
        ]);
        setIsReconnecting(true);
        setIsLoading(false);
      };
    };

    const attemptReconnect = () => {
      if (reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current += 1;
        setTimeout(() => {
          if (!ws.current || ws.current.readyState === WebSocket.CLOSED) {
            connectWebSocket();
          }
        }, 5000);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Failed to reconnect after multiple attempts. Please refresh the page." }
        ]);
        setIsReconnecting(false);
      }
    };

    connectWebSocket();

    return () => {
      ws.current?.close();
    };
  }, [userId, token]);

  const sendMessage = () => {
    if (!input.trim() || !ws.current || ws.current.readyState !== WebSocket.OPEN) {
      if (ws.current && ws.current.readyState !== WebSocket.OPEN) {
        setMessages((prev) => [...prev, { role: "assistant", content: "Reconnecting... Please wait." }]);
      }
      return;
    }
    const userMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    ws.current.send(JSON.stringify({ message: input }));
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") sendMessage();
  };

  return (
    <div className="chatbot-container">
      {!isOpen ? (
        <motion.button
          className="chatbot-toggle submit-button"
          onClick={() => setIsOpen(true)}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          aria-label="Open Chatbot"
        >
          💬 Chat with HR Assistant
        </motion.button>
      ) : (
        <motion.div
          className="chatbot-window control-panel"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <div className="chatbot-header">
            <h3 className="section-title">HR Assistant</h3>
            <button onClick={() => setIsOpen(false)} className="chatbot-close" aria-label="Close Chatbot">✖</button>
          </div>
          <div className="chatbot-messages">
            {messages.map((msg, index) => (
              <motion.div
                key={index}
                className={`message ${msg.role === "user" ? "user" : "assistant"}`}
                initial={{ opacity: 0, x: msg.role === "user" ? 20 : -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2 }}
              >
                {msg.content}
              </motion.div>
            ))}
            {isLoading && <div className="loading">Typing...</div>}
            {isReconnecting && !isLoading && (
              <div className="reconnecting">Reconnecting... Attempt {reconnectAttempts.current} of {maxReconnectAttempts}</div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="chatbot-input">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask me anything..."
              className="modern-input"
              disabled={isLoading || isReconnecting || !userId || !token}
              aria-label="Message Input"
            />
            <motion.button
              onClick={sendMessage}
              disabled={isLoading || isReconnecting || !userId || !token}
              className="submit-button"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              aria-label="Send Message"
            >
              Send
            </motion.button>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default Chatbot;