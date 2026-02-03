"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Plus, Trash2, Github, AlertTriangle, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getSessions, deleteSession, getCurrentUser } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

interface Session {
    id: number;
    name: string;
    repo_url: string;
    created_at: string;
    last_message: string;
}

export default function Sidebar({ currentSessionId }: { currentSessionId?: number }) {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [deleteId, setDeleteId] = useState<number | null>(null);
    const [user, setUser] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [isNewChatOpen, setIsNewChatOpen] = useState(false);
    const [newRepoUrl, setNewRepoUrl] = useState("");
    const router = useRouter();

    useEffect(() => {
        getCurrentUser().then(u => {
            setUser(u);
            setLoading(false);
        });
    }, []);

    const loadSessions = async () => {
        if (!user) return;
        try {
            const data = await getSessions();
            setSessions(data);
        } catch (e) {
            console.error("Failed to load sessions", e);
        }
    };

    useEffect(() => {
        if (user) {
            loadSessions();
        }
    }, [currentSessionId, user]);

    const handleDelete = async () => {
        if (deleteId) {
            try {
                await deleteSession(deleteId);
                await loadSessions();
                if (currentSessionId === deleteId) {
                    router.push('/');
                }
            } catch (e) {
                console.error("Failed to delete", e);
            } finally {
                setDeleteId(null);
            }
        }
    };

    const handleNewChat = () => {
        if (!newRepoUrl) return;
        const encoded = encodeURIComponent(newRepoUrl);
        setIsNewChatOpen(false);
        setNewRepoUrl("");
        router.push(`/chat?repo=${encoded}`);
    };

    if (loading) return <div className="w-64 bg-zinc-950 border-r border-zinc-800" />;

    if (!user) {
        return (
            <div className="w-64 bg-zinc-950 border-r border-zinc-800 flex flex-col items-center justify-center p-6 gap-6 h-full">
                <div className="flex flex-col items-center gap-2">
                    <Github className="w-12 h-12 text-white" />
                    <h2 className="text-xl font-bold text-white mt-2">GitHub RAG</h2>
                    <p className="text-zinc-500 text-center text-sm leading-relaxed">
                        Sign in to save your chat history and manage your repositories securely.
                    </p>
                </div>
                <Button
                    onClick={() => window.location.href = 'http://localhost:8000/login'}
                    className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium h-10 transition-all"
                >
                    Login with Google
                </Button>
            </div>
        );
    }

    return (
        <div className="w-64 bg-zinc-950 border-r border-zinc-800 flex flex-col h-full">
            <div className="p-4 border-b border-zinc-800 flex-shrink-0">
                <Dialog open={isNewChatOpen} onOpenChange={setIsNewChatOpen}>
                    <DialogTrigger asChild>
                        <Button
                            className="w-full bg-white text-black hover:bg-zinc-200 transition-colors flex items-center justify-center gap-2 font-medium"
                        >
                            <Plus size={16} /> New Chat
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="bg-zinc-900 border-zinc-800 text-white sm:max-w-md">
                        <DialogHeader>
                            <DialogTitle>Start New Chat</DialogTitle>
                            <DialogDescription className="text-zinc-400">
                                Enter a GitHub repository URL to start chatting.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="flex items-center space-x-2 my-2">
                            <Input
                                placeholder="https://github.com/owner/repo"
                                value={newRepoUrl}
                                onChange={(e) => setNewRepoUrl(e.target.value)}
                                className="bg-zinc-950 border-zinc-800 text-white placeholder:text-zinc-600 focus-visible:ring-blue-500"
                                onKeyDown={(e) => e.key === 'Enter' && handleNewChat()}
                            />
                        </div>
                        <DialogFooter className="sm:justify-start">
                            <Button
                                type="button"
                                className="w-full bg-blue-600 hover:bg-blue-500 text-white"
                                onClick={handleNewChat}
                            >
                                Start Chatting
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 overflow-y-auto p-2 min-h-0">
                <div className="space-y-1">
                    <p className="px-2 text-xs font-semibold text-zinc-500 mb-2 mt-2 uppercase tracking-wide">
                        History
                    </p>
                    {sessions.length === 0 && (
                        <div className="text-zinc-600 text-xs px-2 italic">No conversations yet</div>
                    )}
                    {sessions.map((session) => (
                        <div
                            key={session.id}
                            className={cn(
                                "group relative flex items-start gap-2 p-2 rounded-lg text-left transition-colors text-sm",
                                currentSessionId === session.id
                                    ? "bg-blue-600/10 text-blue-400"
                                    : "hover:bg-zinc-900 text-zinc-400 hover:text-zinc-200"
                            )}
                        >
                            <button
                                onClick={() => router.push(`/chat?session=${session.id}`)}
                                className="flex-1 flex items-start gap-2 min-w-0"
                            >
                                <MessageSquare size={16} className="mt-0.5 shrink-0" />
                                <div className="overflow-hidden text-left">
                                    <div className="font-medium truncate">{session.name}</div>
                                    <div className="text-xs text-zinc-500 truncate">{session.repo_url.split('/').pop()}</div>
                                </div>
                            </button>

                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setDeleteId(session.id);
                                }}
                                className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-red-400 hover:bg-red-400/10 rounded transition-all"
                                title="Delete Chat"
                            >
                                <Trash2 size={14} />
                            </button>
                        </div>
                    ))}
                </div>
            </div>

            {/* User Profile Footer */}
            <div className="p-3 border-t border-zinc-800 flex items-center gap-3 bg-zinc-950">
                <Avatar className="w-8 h-8 border border-zinc-800">
                    <AvatarImage src={user.picture} />
                    <AvatarFallback className="bg-blue-900 text-blue-200">{user.name?.[0]}</AvatarFallback>
                </Avatar>
                <div className="flex-1 overflow-hidden min-w-0">
                    <div className="text-sm font-medium text-zinc-200 truncate">{user.name}</div>
                    <div className="text-xs text-zinc-500 truncate">{user.email}</div>
                </div>
                <button
                    onClick={() => window.location.href = 'http://localhost:8000/logout'}
                    className="text-zinc-500 hover:text-red-400 transition-colors p-1"
                    title="Logout"
                >
                    <LogOut size={16} />
                </button>
            </div>

            <AlertDialog open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
                <AlertDialogContent className="bg-zinc-900 border-zinc-800 text-white">
                    <AlertDialogHeader>
                        <AlertDialogTitle className="flex items-center gap-2">
                            <AlertTriangle className="text-red-500 w-5 h-5" /> Delete Chat?
                        </AlertDialogTitle>
                        <AlertDialogDescription className="text-zinc-400">
                            This action cannot be undone. This will permanently delete the chat history for this session.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700 hover:text-white">Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700 text-white border-none">Delete</AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div >
    );
}
