"use client";

import { useEffect, useState, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function GraphView({ repoUrl }: { repoUrl: string }) {
    const [graphData, setGraphData] = useState({ nodes: [], links: [] });
    const [loading, setLoading] = useState(true);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!repoUrl) return;

        const fetchGraph = async () => {
            setLoading(true);
            try {
                // Assuming your backend is running on 8000
                const res = await fetch(`http://localhost:8000/graph?repo_url=${encodeURIComponent(repoUrl)}`, { credentials: 'include' });
                const data = await res.json();
                setGraphData(data);
            } catch (e) {
                console.error("Failed to load graph", e);
            } finally {
                setLoading(false);
            }
        };

        fetchGraph();
    }, [repoUrl]);

    if (loading) return <div className="text-zinc-500 p-10 text-center animate-pulse">Analyzing dependency graph...</div>;

    // Group colors
    const colors = { 1: "#71717a", 2: "#3b82f6", 3: "#eab308", 4: "#ec4899", 5: "#a855f7" };

    return (
        <div ref={containerRef} className="w-full h-full bg-zinc-950 overflow-hidden rounded-xl border border-zinc-800 relative">
            <div className="absolute top-4 left-4 z-10 bg-zinc-900/80 p-2 rounded text-xs text-zinc-400 backdrop-blur">
                <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-blue-500"></span> Python</div>
                <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-yellow-500"></span> JS/TS</div>
                <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-pink-500"></span> Style</div>
            </div>

            {/* Dynamic Import wrapper or just use it directly if nextjs allows (needs no-ssr usually) */}
            <ForceGraph2D
                width={containerRef.current?.offsetWidth || 800}
                height={containerRef.current?.offsetHeight || 600}
                graphData={graphData}
                nodeLabel="name"
                nodeColor={(node: { group: number }) => colors[node.group as keyof typeof colors] || "#fff"}
                linkColor={() => "#52525b"}
                backgroundColor="#09090b"
                nodeRelSize={6}
                linkDirectionalArrowLength={3.5}
                linkDirectionalArrowRelPos={1}
            />
        </div>
    );
}
