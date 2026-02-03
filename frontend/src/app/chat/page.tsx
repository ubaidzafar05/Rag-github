"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import ChatWindow from "@/components/ChatWindow";
import dynamic from 'next/dynamic'; // For no-ssr graph
import { ingestRepoAsync, getIngestStatus, createSession, getSession } from "@/lib/api";
import { Loader2, AlertCircle, Network, MessageSquare, FolderGit2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

// Dynamically import GraphView with NO SSR to prevent window errors
const GraphView = dynamic(() => import('@/components/GraphView'), { ssr: false });

function ChatPageContent() {
    const searchParams = useSearchParams();
    const repoUrl = searchParams.get("repo");
    const docsUrl = searchParams.get("docs");
    const sessionParam = searchParams.get("session");
    const router = useRouter();

    const [status, setStatus] = useState<"loading" | "ready" | "error" | "unauthenticated">("loading");
    const [errorMsg, setErrorMsg] = useState("");
    const [sessionId, setSessionId] = useState<number | undefined>(undefined);
    const [activeTab, setActiveTab] = useState<"chat" | "graph">("chat");
    const [activeRepoUrl, setActiveRepoUrl] = useState<string | null>(repoUrl);
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [ingestStep, setIngestStep] = useState("Queued");

    useEffect(() => {
        // If session ID is provided directly, we assume it exists and just load it.
        if (sessionParam) {
            // eslint-disable-next-line
            setSessionId(parseInt(sessionParam));
            setStatus("ready");
            return;
        }

        const initIngestion = async () => {
            try {
                // 0. Check Auth First
                const user = await import("@/lib/api").then(m => m.getCurrentUser());
                if (!user) {
                    setStatus("unauthenticated");
                    return;
                }

                let currentRepoUrl = repoUrl;

                // 1. Resolve Session / Repo URL
                if (sessionParam && !repoUrl) {
                    const sessionData = await getSession(parseInt(sessionParam));
                    currentRepoUrl = sessionData.repo_url;
                    setActiveRepoUrl(sessionData.repo_url);
                }

                if (!currentRepoUrl) throw new Error("No repository URL found for this session.");

                // 2. Create Session (if new)
                if (!sessionParam && repoUrl) {
                    const repoName = repoUrl.split('/').pop() || "Repo Chat";
                    const session = await createSession(repoUrl, repoName);
                    setSessionId(session.id);
                } else if (sessionParam) {
                    setSessionId(parseInt(sessionParam));
                }

                // 3. Ingest (async)
                const job = await ingestRepoAsync(currentRepoUrl, docsUrl || undefined);
                setIngestStep("Cloning repository");
                const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
                while (true) {
                    const status = await getIngestStatus(job.job_id);
                    if (status.status === "completed") {
                        setIngestStep("Completed");
                        setStatus("ready");
                        break;
                    }
                    if (status.status === "failed") {
                        throw new Error(status.message || "Failed to ingest repository.");
                    }
                    setIngestStep(status.message || "Indexing repository");
                    await sleep(1500);
                }
            } catch (err) {
                console.error(err);
                if (err instanceof Error && err.message.includes("401")) {
                    setStatus("unauthenticated");
                    return;
                }
                setStatus("error");
                const message = err instanceof Error ? err.message : "Failed to ingest repository.";
                setErrorMsg(message);
            }
        };

        if (repoUrl || sessionParam) {
            initIngestion();
        } else {
            setStatus("error");
            setErrorMsg("No repository URL provided.");
        }
    }, [repoUrl, docsUrl, sessionParam]);

    if (status === "unauthenticated") {
        return (
            <div className="min-h-screen bg-black text-white flex flex-col items-center justify-center p-4">
                <div className="w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center space-y-6 shadow-2xl">
                    <div className="mx-auto w-16 h-16 bg-blue-900/30 rounded-full flex items-center justify-center border border-blue-500/30">
                        <AlertCircle className="w-8 h-8 text-blue-400" />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold text-white">Login Required</h2>
                        <p className="text-zinc-400 mt-2 text-sm leading-relaxed">
                            You must be logged in to create a chat session for <br />
                            <span className="text-blue-400 font-mono bg-blue-950/50 px-1 py-0.5 rounded">{repoUrl?.split('/').pop()}</span>
                        </p>
                    </div>
                    <Button
                        onClick={() => window.location.href = 'http://localhost:8000/login'}
                        className="w-full h-12"
                    >
                        Sign in with Google
                    </Button>
                    <Button
                        variant="ghost"
                        onClick={() => router.push('/')}
                        className="text-zinc-500 hover:text-zinc-300 text-sm"
                    >
                        Go back home
                    </Button>
                </div>
            </div>
        );
    }

    if (status === "loading") {
        return (
            <div className="min-h-screen bg-black text-white flex flex-col items-center justify-center p-4">
                <div className="text-center space-y-4">
                    <div className="relative mx-auto w-16 h-16">
                        <div className="absolute inset-0 bg-blue-500 rounded-full opacity-20 animate-ping"></div>
                        <div className="relative flex items-center justify-center w-full h-full bg-zinc-900 rounded-full border border-zinc-800">
                            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                        </div>
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
                            Ingesting Repository
                        </h2>
                        <p className="text-zinc-500 mt-2">{ingestStep}</p>
                    </div>
                </div>
            </div>
        );
    }

    if (status === "error") {
        return (
            <div className="min-h-screen bg-black text-white flex items-center justify-center p-4">
                <Alert variant="destructive" className="max-w-md border-red-900 bg-red-950/50">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>{errorMsg}</AlertDescription>
                </Alert>
            </div>
        );
    }

    return (
        <div className="h-screen bg-black text-white flex overflow-hidden relative">
            {/* Mobile Sidebar Overlay */}
            {isSidebarOpen && (
                <div
                    className="absolute inset-0 bg-black/80 z-40 md:hidden"
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            {/* Sidebar - Hidden on mobile unless open */}
            <div className={`
                fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-300 ease-in-out md:relative md:translate-x-0
                ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
            `}>
                <Sidebar currentSessionId={sessionId} />
            </div>

            <div className="flex-1 flex flex-col min-w-0 w-full">
                <div className="p-4 border-b border-zinc-800 flex items-center justify-between bg-zinc-950/50 backdrop-blur z-10">
                    <div className="flex items-center gap-3">
                        <button
                            className="md:hidden p-2 -ml-2 text-zinc-400 hover:text-white"
                            onClick={() => setIsSidebarOpen(true)}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" /></svg>
                        </button>
                        <div>
                            <h1 className="text-xl font-bold">Repository Chat</h1>
                            <div className="flex items-center gap-2 mt-1">
                                <span className="text-xs text-zinc-500 truncate max-w-[200px] md:max-w-md">
                                    {activeRepoUrl || `Session #${sessionId}`}
                                </span>
                                {activeRepoUrl && (
                                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-200 border border-zinc-700">
                                        {activeRepoUrl.split('/').pop()}
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* View Toggles */}
                    <div className="flex bg-zinc-900 rounded-lg p-1 border border-zinc-800">
                        <button
                            onClick={() => setActiveTab("chat")}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-all ${activeTab === 'chat' ? 'bg-zinc-800 text-white shadow' : 'text-zinc-500 hover:text-zinc-300'}`}
                        >
                            <MessageSquare size={14} /> <span className="hidden sm:inline">Chat</span>
                        </button>
                        <button
                            onClick={() => setActiveTab("graph")}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-all ${activeTab === 'graph' ? 'bg-zinc-800 text-white shadow' : 'text-zinc-500 hover:text-zinc-300'}`}
                        >
                            <Network size={14} /> <span className="hidden sm:inline">Graph</span>
                        </button>
                    </div>
                </div>
                <div className="flex-1 overflow-hidden p-4 relative">
                    {/* Render both but hide one to preserve state if needed, or simple conditional */}
                    <div className={`h-full ${activeTab === 'chat' ? 'block' : 'hidden'}`}>
                        {sessionId && <ChatWindow sessionId={sessionId} />}
                    </div>

                    {activeTab === 'graph' && (
                        <div className="h-full animate-in fade-in zoom-in-95 duration-300">
                            {activeRepoUrl ? (
                                <GraphView repoUrl={activeRepoUrl} />
                            ) : (
                                <div className="h-full flex flex-col items-center justify-center text-zinc-500 gap-3">
                                    <div className="w-12 h-12 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center">
                                        <FolderGit2 className="w-6 h-6 text-zinc-400" />
                                    </div>
                                    <div className="text-sm">Graph unavailable without a repository URL.</div>
                                    <Button variant="outline" size="sm" onClick={() => router.push('/')}>
                                        Re-ingest a repo
                                    </Button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default function ChatPage() {
    return (
        <Suspense fallback={<div className="h-screen bg-black text-white flex items-center justify-center">Loading...</div>}>
            <ChatPageContent />
        </Suspense>
    );
}
