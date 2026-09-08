// src/components/LiquidCard.jsx
import React from 'react';

export default function LiquidCard({ item, isResonance, isHero, onSelect }) {
  const isUp = item.change >= 0;
  const netValue = isResonance ? (item.flow || item.total_flow) : (item.flow || item.total_flow || 0);
  const isNetIn = item.is_net_in ?? (netValue >= 0);

  const threshold = isResonance ? 1.5 : isHero ? 5.0 : 2.0;
  const isStrong = Math.abs(netValue) >= threshold;

  let waveColor = '#f1f5f9';
  if (isNetIn) {
    waveColor = isStrong ? '#f87171' : '#FDB4B4'; // 🔥 深紅 / 淺紅
  } else {
    waveColor = isStrong ? '#10b981' : '#63E9AA'; // ❄️ 深綠 / 淺綠
  }
  
  const fillLevel = Math.min((item.flow || item.total_flow) * 2.5 + 15, 95);
  const encodedColor = encodeURIComponent(waveColor);
  const waveSvg = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 20'%3E%3Cpath d='M0 10 Q100 0 200 10 T400 10 L400 20 L0 20 Z' fill='${encodedColor}'/%3E%3C/svg%3E`;
  
  let containerClass = "relative overflow-hidden transition-all duration-300 shadow-md border border-slate-100 ";
  let paddingClass = "p-5";
  
  if (isResonance) containerClass += "bg-white rounded-[28px] min-h-[190px] col-span-2 lg:col-span-1";
  else if (isHero) { containerClass += "bg-white rounded-[24px] aspect-square hover:shadow-xl"; paddingClass = "p-6"; }
  else { containerClass += "bg-white rounded-2xl aspect-square p-2"; paddingClass = "p-3"; }
  
  if (onSelect) containerClass += " cursor-pointer hover:-translate-y-0.5 hover:shadow-xl";

  return (
    <div className={containerClass} onClick={onSelect}>
      <div className="absolute bottom-0 left-0 w-full transition-all duration-[2s] ease-in-out z-0" style={{ height: `${fillLevel}%`, backgroundColor: waveColor }}>
        <div className="absolute top-[-15px] left-0 w-[200%] h-5 animate-waveSlide" style={{ backgroundImage: `url("${waveSvg}")`, backgroundSize: '50% 100%' }}></div>
      </div>
      <div className={`relative z-10 h-full flex flex-col pointer-events-none ${paddingClass}`}>
        <div className="flex justify-between items-start">
          <span className="text-[10px] font-black tracking-wide text-slate-500 truncate max-w-[70%]">{isResonance ? 'Resonance' : (item.main || '')}</span>
          <span className={`font-black bg-white/80 px-1.5 py-0.5 rounded shadow-sm border border-white/50 ${isUp ? 'text-red-500' : 'text-emerald-600'} ${isHero ? 'text-[11px]' : 'text-[9px]'}`}>{isUp ? '▲' : '▼'} {Math.abs(item.change).toFixed(2)}%</span>
        </div>
        <div className={`flex-1 min-h-0 flex flex-col items-start overflow-hidden ${isResonance ? 'justify-start pt-3' : isHero ? 'justify-center mt-0' : 'justify-center mt-1'}`}>
          <h4 className={`font-black text-slate-900 leading-tight tracking-tighter max-w-full break-words [overflow-wrap:anywhere] ${isResonance ? 'text-xl line-clamp-1' : isHero ? 'text-2xl line-clamp-3' : 'text-[13px] line-clamp-4'}`}>
            {item.name}
            {isResonance && (item.id || item.code) && (
              <span className="text-sm font-medium text-slate-400 ml-1.5 tracking-normal">{item.id || item.code}</span>
            )}
          </h4>
          <div className="flex items-baseline gap-0.5">
            <span className={`font-black tracking-tighter text-slate-900 ${isResonance ? 'text-4xl' : isHero ? 'text-5xl' : 'text-xl'}`}>
              {item.flow || item.total_flow}
            </span>
            <span className={`font-black text-slate-900/60 ${isHero ? 'text-lg' : 'text-[9px]'}`}>
              {isResonance ? '億' : '%'}
            </span>
          </div>
        </div>
        <div className={isResonance ? "mt-2" : isHero ? "mt-4" : "mt-1"}>
          {isResonance ? (
            <div className="flex flex-wrap gap-1">
              {item.sectors && item.sectors.slice(0, 3).map((s, i) => <span key={i} className="bg-white/85 text-slate-900 px-2 py-1 rounded-md text-[9px] font-black shadow-sm border border-white/50 max-w-full truncate">{s}</span>)}
            </div>
          ) : (
            <div className="bg-white/85 backdrop-blur-sm rounded-lg px-2.5 py-1 inline-block max-w-full shadow-sm border border-white/60">
              <p className={`font-black tracking-normal leading-snug text-slate-900 ${isHero ? 'text-[12px]' : 'text-[9px]'} break-words [overflow-wrap:anywhere] line-clamp-2`}>{item.path}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}