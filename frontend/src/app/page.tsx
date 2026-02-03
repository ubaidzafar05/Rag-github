"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Github, ArrowRight, Sparkles } from "lucide-react";
import { getCurrentUser } from "@/lib/api";

export default function Home() {
    const [repoUrl, setRepoUrl] = useState("");
    const [user, setUser] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    // Check auth on mount
    useEffect(() => {
        getCurrentUser().then(u => {
            setUser(u);
            setLoading(false);
        });
    }, []);

    const handleStart = () => {
        if (!user) {
            window.location.href = 'http://localhost:8000/login';
            return;
        }
        if (!repoUrl) return;
        const encoded = encodeURIComponent(repoUrl);
        router.push(`/chat?repo=${encoded}`);
    };

    return (
        <div className="min-h-screen bg-black text-white flex flex-col items-center justify-center p-4 relative overflow-hidden">
            {/* Background Gradients */}
            <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] bg-purple-600/30 rounded-full blur-[100px]" />
            <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] bg-blue-600/30 rounded-full blur-[100px]" />

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8 }}
                className="w-full max-w-2xl z-10"
            >
                <Card className="bg-zinc-900/50 border-zinc-800 backdrop-blur-md shadow-2xl">
                    <CardHeader className="text-center">
                        <div className="mx-auto mb-4 bg-zinc-800 p-3 rounded-full w-fit">
                            <Github className="w-8 h-8 text-white" />
                        </div>
                        <CardTitle className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
                            GitHub Repo Bot
                        </CardTitle>
                        <CardDescription className="text-lg text-zinc-400 mt-2">
                            Chat with any repository instantly. Powered by Gemini 2.5 Flash.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="space-y-2">
                            <div className="relative group">
                                <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg blur opacity-30 group-hover:opacity-75 transition duration-1000 group-hover:duration-200"></div>
                                <Input
                                    placeholder="https://github.com/username/repo"
                                    value={repoUrl}
                                    onChange={(e) => setRepoUrl(e.target.value)}
                                    className="relative bg-zinc-950 border-zinc-800 text-white placeholder:text-zinc-600 h-12 text-lg focus-visible:ring-offset-0 focus-visible:ring-1 focus-visible:ring-blue-500"
                                />
                            </div>
                        </div>

                        <Button
                            onClick={handleStart}
                            disabled={loading}
                            className={`w-full h-12 text-lg transition-all font-medium ${!user
                                ? 'bg-blue-600 hover:bg-blue-500 text-white'
                                : 'bg-white text-black hover:bg-zinc-200'
                                }`}
                        >
                            <Sparkles className={`w-5 h-5 mr-2 ${!user ? 'text-white' : 'text-purple-600'}`} />
                            {loading ? 'Checking...' : (!user ? 'Login to Start' : 'Start Chatting')}
                            <ArrowRight className="w-5 h-5 ml-2 opacity-50" />
                        </Button>

                        <div className="flex justify-center gap-4 text-xs text-zinc-600 mt-4">
                            <span>Powered by Repomix</span>
                            <span>•</span>
                            <span>Gemini 2.5 Flash</span>
                        </div>
                    </CardContent>
                </Card>
            </motion.div>
        </div>
    );
}
