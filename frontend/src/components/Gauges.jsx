// src/components/Gauges.jsx
import React from 'react';

// 📊 1. 恐貪指針
export const SentimentGauge = ({ score = 50 }) => {
    const s = Math.min(Math.max(score, 0), 100);
    const segments = [
        { width: '25%', color: "#fca5a5", label: "極度恐懼", eng: "EXTREME FEAR" },
        { width: '20%', color: "#fecaca", label: "恐懼", eng: "FEAR" },
        { width: '10%', color: "#e2e8f0", label: "中立", eng: "NEUTRAL" },
        { width: '20%', color: "#bbf7d0", label: "貪婪", eng: "GREED" },
        { width: '25%', color: "#86efac", label: "極度貪婪", eng: "EXTREME GREED" }
    ];
    return (
        <div className="w-full px-2 py-4">
            <div className="flex w-full mb-1.5 text-[10px] font-black text-slate-500 uppercase tracking-tighter">
                <div className="w-[25%] text-center">極度恐懼</div>
                <div className="w-[20%] text-center">恐懼</div>
                <div className="w-[10%] text-center">中立</div>
                <div className="w-[20%] text-center">貪婪</div>
                <div className="w-[25%] text-center">極度貪婪</div>
            </div>
            <div className="relative h-2 w-full flex rounded-full overflow-hidden border border-slate-50">
                {segments.map((seg, i) => (
                    <div key={i} style={{ width: seg.width, backgroundColor: seg.color }} className="h-full" />
                ))}
            </div>
            <div className="relative w-full h-6 mt-0.5">
                <div className="absolute transition-all duration-1000 ease-out flex flex-col items-center" style={{ left: `${s}%`, transform: 'translateX(-50%)' }}>
                    <div className="w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-b-[7px] border-b-slate-600"></div>
                    <div className="text-xl font-black font-mono text-slate-600 leading-none mt-1">{s}</div>
                </div>
            </div>
        </div>
    );
};

// 📈 2. 融資維持率弧形針
export const MarginRatioGauge = ({ ratio = 0 }) => {
    const r = parseFloat(ratio) || 0;
    const radius = 22;
    const circumference = radius * Math.PI;
    const offset = circumference - (Math.min(Math.max(r / 20, 0), 1) * circumference); return (
        <div className="flex flex-col items-center justify-center">
            <div className="relative w-24 h-14">
                <svg viewBox="0 0 50 30" className="w-full h-full">
                    <path d="M 5 28 A 20 20 0 0 1 45 28" fill="none" stroke="#f1f5f9" strokeWidth="6" strokeLinecap="round" />
                    <path d="M 5 28 A 20 20 0 0 1 45 28" fill="none" stroke={r > 15 ? "#ef4444" : r > 8 ? "#f59e0b" : "#6366f1"} strokeWidth="6" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} className="transition-all duration-1000 ease-out" />
                    <text x="50%" y="25" textAnchor="middle" fontSize="10" fontWeight="900" fill="#1e293b" className="font-mono">{r}%</text>
                </svg>
            </div>
            <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest -mt-2">全市場</span>
        </div>
    );
};