"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, FileCode, Sparkles, Bug, FileText, Check, X, Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import ReactMarkdown from "react-markdown";
import mermaid from "mermaid";
import { sendChatMessage, getSessionMessages, applyFix } from "@/lib/api";
import { cn } from "@/lib/utils";

mermaid.initialize({ startOnLoad: false, theme: 'dark' });

const ApplyBlock = ({ code_block, repoUrl }: { code_block: string, repoUrl: string }) => {
    const pathMatch = code_block.match(/<file path="([^"]+)">/);
    const filePath = pathMatch ? pathMatch[1] : "unknown";
    const content = code_block.replace(/<file path="[^"]+">/, "").replace("</file>", "").trim();

    const [status, setStatus] = useState<"idle" | "applying" | "success" | "error">("idle");

    const handleApply = async () => {
        setStatus("applying");
        try {
            await applyFix(repoUrl, filePath, content);
            setStatus("success");
        } catch {
            setStatus("error");
        }
    };

    return (
        <div className="my-4 rounded-lg overflow-hidden border border-zinc-700 bg-zinc-900">
            <div className="flex items-center justify-between px-4 py-2 bg-zinc-800 border-b border-zinc-700">
                <div className="flex items-center gap-2 text-sm font-mono text-zinc-300">
                    <FileCode size={14} className="text-blue-400" />
                    {filePath}
                </div>
                {status === "idle" && (
                    <Button size="sm" onClick={handleApply} className="h-7 text-xs bg-blue-600 hover:bg-blue-500">
                        <Terminal size={12} className="mr-1" /> Apply Fix
                    </Button>
                )}
                {status === "applying" && <span className="text-xs text-zinc-400 animate-pulse">Applying...</span>}
                {status === "success" && <span className="text-xs text-green-400 flex items-center gap-1"><Check size={12} /> Applied</span>}
                {status === "error" && <span className="text-xs text-red-400 flex items-center gap-1"><X size={12} /> Failed</span>}
            </div>
            <div className="p-0 bg-zinc-950 overflow-x-auto">
                <pre className="p-3 text-xs font-mono text-zinc-300 leading-relaxed">{content}</pre>
            </div>
        </div>
    );
};

const MermaidBlock = ({ code }: { code: string }) => {
    const [svg, setSvg] = useState("");

    useEffect(() => {
        const render = async () => {
            try {
                // Clean code: remove backticks if present (sometimes LLMs include them)
                const cleanCode = code.replace(/`/g, "").trim();
                const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
                const { svg } = await mermaid.render(id, cleanCode);
                setSvg(svg);
            } catch (e) {
                console.error("Mermaid Render Error:", e);
                setSvg(`<div class='p-2 border border-red-900 bg-red-950/30 rounded text-red-400 text-xs font-mono'><p class='font-bold'>Diagram Error:</p>${e instanceof Error ? e.message : String(e)}</div>`);
            }
        };
        render();
    }, [code]);

    return <div className="my-4 bg-zinc-950 p-4 rounded-lg overflow-x-auto" dangerouslySetInnerHTML={{ __html: svg }} />;
};

interface Message {
    role: "user" | "model";
    content: string;
}

export default function ChatWindow({ sessionId, repoUrl }: { sessionId?: number, repoUrl: string }) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [messages]);

    useEffect(() => {
        const loadHistory = async () => {
            if (sessionId) {
                try {
                    const history = await getSessionMessages(sessionId);
                    setMessages(history.length > 0 ? history : [{ role: "model", content: "Hello! I've analyzed the repository. Ask me anything about the code." }]);
                } catch (e) {
                    console.error("Failed to load history", e);
                }
            }
        };
        loadHistory();
    }, [sessionId]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMsg: Message = { role: "user", content: input };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setIsLoading(true);

        try {
            const history = messages.map(m => ({ role: m.role, parts: [m.content] }));
            const response = await sendChatMessage(userMsg.content, history, sessionId);

            setMessages(prev => [...prev, { role: "model", content: response.response || response }]);
        } catch {
            setMessages(prev => [...prev, { role: "model", content: "Error: Failed to get response." }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleQuickAction = (action: string) => {
        let prompt = "";
        switch (action) {
            case "explain": prompt = "Explain the high-level architecture of this system and include a Mermaid diagram."; break;
            case "bugs": prompt = "Scan the codebase for potential bugs or security issues."; break;
            case "docs": prompt = "Generate a brief documentation summary for this repository."; break;
        }
        if (prompt) {
            setInput(prompt);
        }
    };

    // Helper to render message content with potential <file> blocks
    const renderContent = (text: string) => {
        const parts = text.split(/(<file path="[^"]+">[\s\S]*?<\/file>)/g);

        return parts.map((part, i) => {
            if (part.startsWith("<file")) {
                return <ApplyBlock key={i} code_block={part} repoUrl={repoUrl} />;
            }
            return (
                <div key={i} className="prose prose-invert prose-sm max-w-none break-words mb-2 last:mb-0">
                    <ReactMarkdown
                        components={{
                            code({ className, children, ...props }) {
                                const match = /language-(\w+)/.exec(className || "");
                                const isMermaid = match && match[1] === "mermaid";
                                if (isMermaid) return <MermaidBlock code={String(children).replace(/\n$/, "")} />;
                                return (
                                    <code className={`${className} bg-zinc-900/50 px-1 py-0.5 rounded text-blue-300 font-mono`} {...props}>
                                        {children}
                                    </code>
                                )
                            }
                        }}
                    >
                        {part}
                    </ReactMarkdown>
                </div>
            );
        });
    };

    return (
        <div className="flex flex-col h-full bg-zinc-950 text-white rounded-xl overflow-hidden border border-zinc-800 shadow-2xl">
            <div className="flex items-center p-4 border-b border-zinc-800 bg-zinc-900/50 backdrop-blur">
                <Bot className="w-5 h-5 mr-2 text-blue-400" />
                <h2 className="font-semibold text-zinc-100">AI Assistant</h2>
            </div>

            <div className="flex-1 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
                <div className="space-y-6">
                    {messages.map((msg, idx) => (
                        <div
                            key={idx}
                            className={cn(
                                "flex gap-3",
                                msg.role === "user" ? "flex-row-reverse" : "flex-row"
                            )}
                        >
                            <Avatar className={cn("w-8 h-8", msg.role === "model" ? "bg-blue-600" : "bg-purple-600")}>
                                <AvatarFallback>{msg.role === "model" ? "AI" : "ME"}</AvatarFallback>
                                <div className="flex items-center justify-center w-full h-full">
                                    {msg.role === "model" ? <Bot size={16} /> : <User size={16} />}
                                </div>
                            </Avatar>

                            <div
                                className={cn(
                                    "p-3 rounded-2xl max-w-[80%] text-sm leading-relaxed",
                                    msg.role === "user"
                                        ? "bg-purple-600 text-white rounded-tr-sm"
                                        : "bg-zinc-800 text-zinc-200 rounded-tl-sm border border-zinc-700"
                                )}
                            >
                                <div className="text-sm leading-relaxed max-w-none break-words">
                                    {renderContent(msg.content)}
                                </div>
                            </div>
                        </div>
                    ))}
                    {isLoading && (
                        <div className="flex gap-3">
                            <Avatar className="w-8 h-8 bg-blue-600">
                                <AvatarFallback>AI</AvatarFallback>
                                <div className="flex items-center justify-center w-full h-full"><Bot size={16} /></div>
                            </Avatar>
                            <div className="bg-zinc-800 p-3 rounded-2xl rounded-tl-sm border border-zinc-700 flex items-center gap-2">
                                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                            </div>
                        </div>
                    )}
                    <div ref={scrollRef} />
                </div>
            </div>

            <div className="p-4 bg-zinc-900/50 border-t border-zinc-800 backdrop-blur space-y-3">
                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-none">
                    <Button size="sm" variant="outline" className="bg-zinc-800 border-zinc-700 text-zinc-300 hover:text-white text-xs gap-2" onClick={() => handleQuickAction('explain')}>
                        <Sparkles size={14} className="text-yellow-400" /> Explain Architecture
                    </Button>
                    <Button size="sm" variant="outline" className="bg-zinc-800 border-zinc-700 text-zinc-300 hover:text-white text-xs gap-2" onClick={() => handleQuickAction('bugs')}>
                        <Bug size={14} className="text-red-400" /> Find Bugs
                    </Button>
                    <Button size="sm" variant="outline" className="bg-zinc-800 border-zinc-700 text-zinc-300 hover:text-white text-xs gap-2" onClick={() => handleQuickAction('docs')}>
                        <FileText size={14} className="text-blue-400" /> Summarize Docs
                    </Button>
                </div>
                <form
                    onSubmit={(e) => { e.preventDefault(); handleSend(); }}
                    className="relative flex gap-2"
                >
                    <Input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask a question about the codebase..."
                        className="bg-zinc-950 border-zinc-700 text-white placeholder:text-zinc-500 focus-visible:ring-blue-500 pr-12"
                    />
                    <Button
                        type="submit"
                        size="icon"
                        disabled={isLoading || !input.trim()}
                        className="absolute right-1 top-1 h-8 w-8 bg-blue-600 hover:bg-blue-500 text-white"
                    >
                        <Send className="w-4 h-4" />
                    </Button>
                </form>
            </div>
        </div>
    );
}
