"use client";
import React, { useState, useRef, useEffect } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import type { Message } from "@langchain/langgraph-sdk";
import { Client } from "@langchain/langgraph-sdk";
import "./App.css";

// 1) Define a wrapper type that includes `additional_kwargs`
type ExtendedMessage = Message & {
  additional_kwargs?: {
    geolocation?: any;
    is_link?: boolean;
    display: boolean;
    complete?: boolean;
  };
};

const App: React.FC = () => {
  const apiUrl = import.meta.env.VITE_DEPLOYMENT_URL;
  const apiKey = import.meta.env.VITE_LANGSMITH_API_KEY;
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isExpanded, setExpanded] = useState<boolean>(false)
  const [message, setMessage] = useState<string>("")
  const bottomMarkerRef = useRef<HTMLDivElement>(null);
  const messageContainer = useRef<HTMLDivElement>(null);
  // const [threads, setThreads] = useState<string[]>([]);
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);

  const initializeThread = async () => {
    if (!localStorage.getItem("current-thread-id")) {
      const client = new Client({ apiUrl: apiUrl, apiKey: apiKey });
      const new_thread = await client.threads.create();
      localStorage.setItem("current-thread-id", new_thread["thread_id"]);
      localStorage.setItem("thread-ids", new_thread["thread_id"]);
      setCurrentThreadId(new_thread["thread_id"])
    } else {
      setCurrentThreadId(localStorage.getItem("current-thread-id"))
    }
  };

  useEffect(() => {
    initializeThread();
  }, []);

  // 2) Use `ExtendedMessage` in the `useStream` hook:
  const thread = useStream<{ messages: ExtendedMessage[] }>({
    apiUrl: apiUrl,
    apiKey: apiKey,
    assistantId: "chatbot",
    messagesKey: "messages",
    threadId: currentThreadId,
  });

  const toggleChatbox = () => {
    setIsOpen((prev) => !prev);
  };
  const toggleSize = () => {
    setExpanded((prev) => !prev)
  }

  const createNewThread = async () => {
    if(thread.isLoading) return;
    const client = new Client({ apiUrl: apiUrl, apiKey: apiKey });
    const new_thread = await client.threads.create();
    localStorage.setItem("current-thread-id", new_thread["thread_id"]);
    setCurrentThreadId(new_thread["thread_id"])
    localStorage.setItem("thread-ids", new_thread["thread_id"]+","+localStorage.getItem("thread-ids"));
  }

  const scrollToBottom = () => {
    if (messageContainer.current) {
      messageContainer.current.scrollTop = messageContainer.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [isOpen, thread.messages, isExpanded]);

  useEffect(() => {
    // 3) Safely check `additional_kwargs` with a type assertion:
    if (
      thread.messages.length > 0 &&
      (thread.messages[thread.messages.length - 1] as ExtendedMessage).additional_kwargs?.geolocation
    ) {
      navigator.geolocation.getCurrentPosition(
        function (position) {
          const latitude = position.coords.latitude;
          const longitude = position.coords.longitude;
          if(!thread.isLoading) {
            thread.submit({
              messages: [{ type: "human", content: "Latitude: "+latitude+",Longitude: "+longitude, additional_kwargs: {display:false} }],
            });
          }
        },
        function (error) {
          console.error("Error getting location: " + error.message);
        }
      );
    }
  }, [thread.messages])

  const submitMessage = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const formData = new FormData(form);
    const message = formData.get("message") as string;
    form.reset();
    if(!thread.isLoading && message) {
      thread.submit({
        messages: [{ type: "human", content: message }],
      });
      setMessage("")
    }
  };

  const changeThread = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setCurrentThreadId(e.target.value)
    localStorage.setItem("current-thread-id", e.target.value)
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && event.ctrlKey) {
      event.preventDefault();
      thread.submit({
        messages: [{ type: "human", content: message }],
      })
      setMessage("")
    }
  };

  return (
    <div className="fixed bottom-4 right-4">
      {isOpen && (
        <div className={`mt-4 ${isExpanded ? "md:w-240" : "md:w-120"}  w-95 bg-white rounded-lg shadow-lg flex flex-col overflow-hidden transition-opacity duration-100 opacity-100`}>
          {/* Chat Header */}
          <div className="bg-blue-500 p-4 flex justify-between items-center">
            <h2 className="text-white text-lg font-semibold">Aposto Chatbot</h2>
            <div className="flex items-center">
              <select onChange={changeThread} className={`text-white ${isExpanded ? "w-auto": "w-40"} max-md:w-30`}>
                {
                  localStorage.getItem("thread-ids")?.split(',').map((id) => {
                    return <option value={id} key={id}>{id}</option>
                  })
                }
              </select>
              <button
                onClick={createNewThread}
                className="bg-transparent text-white p-2 rounded-lg pointer transition cursor-pointer hover:bg-blue-600"
              >
                <svg
                  fill="#ffffff"
                  version="1.1"
                  xmlns="http://www.w3.org/2000/svg"
                  xmlnsXlink="http://www.w3.org/1999/xlink"
                  width="16px"
                  height="16px"
                  viewBox="0 0 45.402 45.402"
                  xmlSpace="preserve"
                  transform="matrix(1, 0, 0, 1, 0, 0)"
                >
                  <g id="SVGRepo_bgCarrier" strokeWidth="0"></g>
                  <g
                    id="SVGRepo_tracerCarrier"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  ></g>
                  <g id="SVGRepo_iconCarrier">
                    <g>
                      <path d="M41.267,18.557H26.832V4.134C26.832,1.851,24.99,0,22.707,0c-2.283,0-4.124,1.851-4.124,4.135v14.432H4.141 c-2.283,0-4.139,1.851-4.138,4.135c-0.001,1.141,0.46,2.187,1.207,2.934c0.748,0.749,1.78,1.222,2.92,1.222h14.453V41.27 c0,1.142,0.453,2.176,1.201,2.922c0.748,0.748,1.777,1.211,2.919,1.211c2.282,0,4.129-1.851,4.129-4.133V26.857h14.435 c2.283,0,4.134-1.867,4.133-4.15C45.399,20.425,43.548,18.557,41.267,18.557z" />
                    </g>
                  </g>
                </svg>
              </button>
              <button
                onClick={toggleSize}
                className="bg-transparent text-white p-2 rounded-lg pointer transition cursor-pointer hover:bg-blue-600 max-md:hidden"
              >
                {
                  isExpanded && (
                    <svg width="16px" height="16px" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="#ffffff"><g id="SVGRepo_bgCarrier" strokeWidth="0"></g><g id="SVGRepo_tracerCarrier" strokeLinecap="round" strokeLinejoin="round"></g><g id="SVGRepo_iconCarrier"> <path d="M14 10L21 3M14 10H20M14 10V4M3 21L10 14M10 14V20M10 14H4" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"></path> </g></svg>
                  )
                }
                {
                  !isExpanded && (
                    <svg width="16px" height="16px" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><g id="SVGRepo_bgCarrier" strokeWidth="0"></g><g id="SVGRepo_tracerCarrier" strokeLinecap="round" strokeLinejoin="round"></g><g id="SVGRepo_iconCarrier"> <path d="M14.5 9.5L21 3M21 3H15M21 3V9M3 21L9.5 14.5M3 21V15M3 21H9" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"></path> </g></svg>
                  )
                }
              </button>
            </div>
          </div>

          {/* Chat Messages Area */}
          <div className={`p-4 ${isExpanded ? "md:h-130" : "md:h-120"} h-95 overflow-y-auto space-y-4`} ref={messageContainer}>
            {thread.messages.map((message, index) => {
              return (
                <div
                  key={index}
                  className={`flex items-start ${message.type === "human" ? "justify-end" : ""}`}
                >
                  {
                  message.type === "ai" && 
                  !(message as ExtendedMessage).additional_kwargs?.is_link &&   (
                    <div className={`bg-gray-200 text-gray-900 p-2 rounded-lg ${isExpanded ? "max-w-220":"max-w-100"}`}>
                      <p dangerouslySetInnerHTML={{__html: message.content as unknown as string}}></p>
                    </div>
                  )}
  
                  {
                  message.type === "ai" && 
                  (message as ExtendedMessage).additional_kwargs?.is_link && (
                    <a
                      target="_blank"
                      href={message.content as string}
                      className="text-blue-500 hover:underline"
                    >
                      {message.content as unknown as React.ReactNode}
                    </a>
                  )}
  
                  {message.type === "human" && (message as ExtendedMessage).additional_kwargs?.display!=false && (
                    <div className={`bg-blue-500 text-white p-2 rounded-lg ${isExpanded ? "max-w-220":"max-w-100"}`}>
                      <p>{message.content as unknown as React.ReactNode}</p>
                    </div>
                  )}
                </div>
              )
            } )}
            <div ref={bottomMarkerRef} />
          </div>

          {/* Chat Input */}
          <form className="border-t p-4 flex relative" onSubmit={submitMessage}>
            {thread.isLoading && (
              <div className="absolute -top-10">
                <div className="text-gray-900 p-2 rounded-lg max-w-xs">
                  <p>digitando...</p>
                </div>
              </div>
            )}
            <textarea
              placeholder="Digita il tuo messaggio..."
              name="message"
              rows={3}
              autoComplete="off"
              value={message}
              className="flex-grow p-2 border border-gray-300 rounded-l-lg focus:outline-none resize-y"
              disabled={thread.isLoading}
              onKeyDown={handleKeyDown}
              onChange={(e) => setMessage(e.target.value)}
            />

            <button
              type="submit"
              disabled={thread.isLoading}
              className="bg-blue-500 text-white px-4 rounded-r-lg hover:bg-blue-600 transition"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-6 w-6 transform -rotate-45"
                fill="currentColor"
                viewBox="0 0 24 24"
              >
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          </form>
        </div>
      )}

      {/* Toggle Chatbox Button */}
      <button
        onClick={toggleChatbox}
        className="bg-blue-500 text-white px-4 py-2 mt-2 rounded-full shadow-lg hover:bg-blue-600 transition float-right"
      >
        {isOpen && (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
        {!isOpen && (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.97-4.03 9-9 9a9.92 9.92 0 01-4-.93L3 21l1.93-4.07A8.959 8.959 0 013 12c0-4.97 4.03-9 9-9s9 4.03 9 9z"
            />
          </svg>
        )}
      </button>
    </div>
  );
};

export default App;
