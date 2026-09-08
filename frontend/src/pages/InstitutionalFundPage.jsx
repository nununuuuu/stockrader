import React, { useState, useEffect } from 'react';
import { SentimentGauge, MarginRatioGauge } from '../components/Gauges';
import { formatBillion, formatK, getVixStatus } from '../utils/format';
// ========================================================
// 🧮 內聚計算函數：不帶狀態的工具函數，直接收納在頁面內部
// ========================================================

const TAG_THEMES = {
  electronics: { bg: "#e0f2fe", text: "#0369a1", border: "#bae6fd", label: "電子" },
  concepts: { bg: "#ffedd5", text: "#c2410c", border: "#fed7aa", label: "概念" },
  group: { bg: "#f3e8ff", text: "#7e22ce", border: "#e9d5ff", label: "集團" },
  basic: { bg: "#f1f5f9", text: "#475569", border: "#e2e8f0", label: "類別" }
};


// ========================================================
// 🏛️ 主頁面組件：Props 乾淨清空，杜絕命名撞車！
// ========================================================
export default function InstitutionalFundPage({ 
  subTab, 
  data, 
  radarData, 
  excludeETF, 
  fetchRadarData,
}) {
  const currentList = data?.rankings?.[subTab] || { tse_b: [], tse_s: [], otc_b: [], otc_s: [] };

  return (
    <div className="animate-fadeIn">
      {/* 🌟 決策級看板：3:3:3:3 佈局完全保留 */}
      <div className="grid grid-cols-12 gap-5 mb-8">

        {/* [卡片 1] Market Price */}
        <div className="col-span-12 lg:col-span-3 bg-white p-5 rounded-[24px] shadow-sm border border-slate-100 flex flex-col justify-between h-[250px]">
          <div>
            <div className="text-slate-400 text-[9px] font-black uppercase tracking-widest mb-1 opacity-70">Market Price</div>
            <div className={`text-3xl font-black mb-1 ${data?.taiex?.diff >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {data?.taiex?.price?.toLocaleString() || "--,---"}
            </div>
            <div className={`flex items-center gap-1.5 text-xs font-black ${data?.taiex?.diff >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {data?.taiex ? <span>{data.taiex.diff >= 0 ? '▲' : '▼'} {Math.abs(data.taiex.diff)} ({data.taiex.pct}%)</span> : <span>-- ( --% )</span>}
            </div>
            <div className="flex flex-wrap gap-2 mt-3 items-center">
              <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${data?.taiex?.is_above_ma20 ? 'bg-red-50 text-red-500 border-red-100' : 'bg-green-50 text-green-600 border-green-100'}`}>MA20</span>
              <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${data?.taiex?.is_above_ma60 ? 'bg-red-50 text-red-500 border-red-100' : 'bg-green-50 text-green-600 border-green-100'}`}>MA60</span>
              <span className="ml-auto text-[10px] font-black text-blue-500 bg-blue-50/50 px-2 py-0.5 rounded border border-blue-100/50">
                量比 {data?.taiex?.vol_ratio ? data.taiex.vol_ratio.toFixed(2) : "--.--"}x
              </span>
            </div>
          </div>
          <div className="space-y-1.5">
            <div className="flex justify-between text-[9px] font-black text-slate-400 uppercase">
              <span className="text-red-500">{data?.breadth?.up || "---"}</span>
              <span className="text-green-600">{data?.breadth?.down || "---"}</span>
            </div>
            <div className="h-2 w-full bg-slate-50 rounded-full flex overflow-hidden border border-slate-100">
              <div className="bg-red-400 transition-all duration-1000" style={{ width: `${(data?.breadth?.up / (data?.breadth?.up + data?.breadth?.down || 1)) * 100 || 50}%` }}></div>
              <div className="bg-green-400 transition-all duration-1000" style={{ width: `${(data?.breadth?.down / (data?.breadth?.up + data?.breadth?.down || 1)) * 100 || 50}%` }}></div>
            </div>
          </div>
        </div>

        {/* [卡片 2] Market Sentiment */}
        <div className="col-span-12 lg:col-span-3 bg-white p-4 rounded-[24px] shadow-sm border border-slate-100 flex flex-col h-[250px] overflow-hidden">
          <div className="text-center"><span className="text-slate-400 text-[9px] font-black uppercase tracking-widest opacity-60">Market Sentiment</span></div>
          {/* 🎯 這裡直接正確呼叫從 /Gauges 引入的獨立元件 */}
          <div className="mt-0"><SentimentGauge score={data?.sentiment?.now?.score} /></div>
          <div className="mt-1 flex flex-col px-1">
            {[
              { label: "昨日", d: data?.sentiment?.last },
              { label: "一週", d: data?.sentiment?.week },
              { label: "一月", d: data?.sentiment?.month }
            ].map((h, i) => (
              <div key={i} className="flex justify-between items-center py-0.5">
                <span className="text-[10px] text-slate-400 font-bold">{h.label}</span>
                <div className="flex items-center gap-2">
                  <span className={`text-[8px] font-black uppercase ${h.d?.score > 55 ? 'text-emerald-500' : h.d?.score < 45 ? 'text-red-400' : 'text-slate-400'}`}>{h.d?.label || "---"}</span>
                  <span className="font-mono font-black text-slate-600 text-[10px] w-6 text-right">{h.d?.score ?? "---"}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-auto pt-2 border-t border-slate-100 flex justify-between items-center">
            <div className="flex flex-col">
              <span className="text-slate-400 text-[8px] font-black uppercase leading-none mb-1">VIX INDEX</span>
              <span className="text-xl font-black font-mono text-slate-700 leading-none">{data?.sentiment?.vix ? data.sentiment.vix.toFixed(2) : "--.--"}</span>
            </div>
            {data?.sentiment?.vix ? <div className={`px-2 py-0.5 text-[10px] font-black rounded border ${getVixStatus(data.sentiment.vix).color}`}>{getVixStatus(data.sentiment.vix).label}</div> : <div className="px-2 py-0.5 bg-slate-50 text-slate-300 text-[8px] font-black rounded border border-slate-100">N/A</div>}
          </div>
        </div>

        {/* [卡片 3] Main Force */}
        <div className="col-span-12 lg:col-span-3 bg-white p-5 rounded-[24px] shadow-sm border border-slate-100 flex flex-col justify-between h-[250px]">
          <div>
            <div className="text-slate-400 text-[9px] font-black uppercase tracking-widest mb-1 opacity-70">Main Force (Net)</div>
            <div className={`text-3xl font-black ${data?.summary?.total >= 0 ? 'text-red-500' : 'text-green-600'}`}>{data?.summary ? formatBillion(data.summary.total) : "--.--"}<span className="text-[20px] ml-0.5 opacity-40">億</span></div>
            <div className="space-y-3.5 mt-4">
              {['foreign', 'trust', 'dealer'].map(k => {
                const val = data?.summary?.[k] || 0;
                const maxVal = Math.max(Math.abs(data?.summary?.foreign || 0), Math.abs(data?.summary?.trust || 0), Math.abs(data?.summary?.dealer || 0), 100);
                const barWidth = (Math.abs(val) / maxVal) * 50;
                return (
                  <div key={k} className="space-y-1">
                    <div className="flex justify-between text-[9px] font-black uppercase"><span className="text-slate-400">{k === 'foreign' ? '外資' : k === 'trust' ? '投信' : '自營'}</span><span className={val >= 0 ? 'text-red-500' : 'text-green-600'}>{formatBillion(val)}</span></div>
                    <div className="relative h-1.5 w-full bg-slate-50 rounded-full overflow-hidden border border-slate-100/50">
                      <div className="absolute left-1/2 top-0 w-px h-full bg-slate-200 z-10" />
                      <div className={`absolute top-0 h-full transition-all duration-1000 ease-out ${val >= 0 ? 'bg-red-400' : 'bg-green-400'}`} style={{ width: `${barWidth}%`, left: val >= 0 ? '50%' : 'auto', right: val < 0 ? '50%' : 'auto' }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="py-2 rounded-xl text-center border border-slate-100 bg-slate-50/80 shadow-sm text-[10px] font-black text-slate-600 uppercase">{data?.signals?.inst || "Wait Sync"}</div>
        </div>

        {/* [卡片 4] Leverage Analysis */}
        <div className="col-span-12 lg:col-span-3 bg-white p-5 rounded-[24px] shadow-sm border border-slate-100 flex flex-col h-[250px] overflow-hidden">
          <div className="text-slate-400 text-[9px] font-black uppercase tracking-widest opacity-70 mb-2">Leverage Analysis</div>
          <div className="flex justify-between items-center flex-1">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="w-1 h-7 bg-orange-400/80 rounded-full" />
                <div className="flex flex-col">
                  <span className="text-[10px] text-slate-400 font-black uppercase leading-none mb-0.5">融資增減</span>
                  <div className={`text-xl font-black font-mono leading-none ${data?.margin?.financing >= 0 ? 'text-red-500' : 'text-green-600'}`}>{(data?.margin && data.margin.financing !== undefined) ? formatBillion(data.margin.financing) : "--.--"}<span className="text-[11px] ml-0.5 opacity-40">億</span></div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1 h-7 bg-indigo-400/80 rounded-full" />
                <div className="flex flex-col">
                  <span className="text-[10px] text-slate-400 font-black uppercase leading-none mb-0.5">融券增減</span>
                  <div className={`text-xl font-black font-mono leading-none ${data?.margin?.short_selling >= 0 ? 'text-red-500' : 'text-green-600'}`}>{(data?.margin && data.margin.short_selling !== undefined) ? formatK(data.margin.short_selling) : "--"}<span className="text-[11px] ml-0.5 opacity-40">張</span></div>
                </div>
              </div>
            </div>
            {/* 🎯 這裡直接正確呼叫從 /Gauges 引入的獨立元件 */}
            <div className="pr-1"><MarginRatioGauge ratio={data?.margin?.ratio} /></div>
          </div>
          <div className="mt-3 flex justify-around items-center py-1 bg-slate-50/50 rounded-lg border border-slate-100/50">
            <div className="flex flex-col items-center"><span className="text-[9px] text-slate-400 font-bold uppercase scale-90">上市</span><span className="text-[10px] font-black font-mono text-slate-600">{data?.margin?.tse_ratio || "---"}%</span></div>
            <div className="w-px h-3 bg-slate-200" /><div className="flex flex-col items-center"><span className="text-[9px] text-slate-400 font-bold uppercase scale-90">上櫃</span><span className="text-[10px] font-black font-mono text-slate-600">{data?.margin?.otc_ratio || "---"}%</span></div>
          </div>
          <div className={`mt-3 py-1.5 rounded-xl text-center border shadow-sm text-[10px] font-black tracking-wider uppercase ${data?.signals?.margin?.includes('💎') ? 'bg-indigo-50 border-indigo-200 text-indigo-600' : 'bg-slate-50 border-slate-100 text-slate-500'}`}>{data?.signals?.margin || "Wait Sync"}</div>
        </div>

      </div>

      {/* 資料內容切換 */}
      <div>
        {subTab === 'radar' && RadarView && <RadarView data={radarData} onScanComplete={fetchRadarData} />}
        {subTab === 'sectors' && SectorView && <SectorView data={data?.sectors} />}
        {['total', 'foreign', 'trust', 'dealer'].includes(subTab) && RankingView && (
          <RankingView list={currentList} type={subTab} excludeETF={excludeETF} data={data} />
        )}
      </div>
    </div>
  );
}

export function RankingView({ list, type, excludeETF, data }) {
  const [expandedId, setExpandedId] = useState(null);
  
  const Table = ({ items, isBuy, title }) => {
    const displayItems = (items || []).filter(i => excludeETF ? !i.is_etf : true);
    return (
      <div className="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100 mb-8 overflow-hidden">
        <h3 className={`font-black mb-6 text-sm uppercase tracking-widest ${isBuy ? 'text-red-500' : 'text-green-600'} flex items-center`}>
          <span className={`w-2 h-2 rounded-full mr-2 ${isBuy ? 'bg-red-500' : 'bg-green-600'}`}></span>{title}
        </h3>
        <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-slate-300 font-black uppercase border-b">
            <tr>
              <th className="pb-4 px-2">股票名稱</th>
              <th className="text-right pb-4 px-4 font-mono">張數</th>
              <th className="text-right pb-4 px-2">主要類別</th>
            </tr>
          </thead>
          <tbody>
            {displayItems.slice(0, 15).map((s) => {
              const isExpanded = expandedId === s.stock_id;
              const mainTagType = Object.keys(TAG_THEMES).find(key => s.all_tags?.[key]?.trim() === s.category?.trim()) || 'basic';
              const mainStyle = TAG_THEMES[mainTagType];
              const otherTags = Object.entries(s.all_tags || {}).filter(([tKey, tName]) => tName && tName.trim() !== s.category?.trim() && TAG_THEMES[tKey]);
              return (
                <React.Fragment key={s.stock_id}>
                  <tr onClick={() => setExpandedId(isExpanded ? null : s.stock_id)} className={`border-b border-slate-50 last:border-0 hover:bg-slate-50 transition cursor-pointer ${isExpanded ? 'bg-slate-50' : ''}`}>
                    <td className="py-4 px-2 font-black text-slate-800 text-base">
                      {s?.stock_name} <span className="text-[10px] text-slate-400 font-mono ml-1 opacity-60 font-bold uppercase">{s?.stock_id}</span>
                    </td>
                    <td className={`text-right font-black text-lg px-4 font-mono ${isBuy ? 'text-red-500' : 'text-green-600'}`}>
                      {formatK(s?.[type] || 0)}
                    </td>
                    <td className="text-right px-2">
                      <span style={{ backgroundColor: mainStyle.bg, color: mainStyle.text, borderColor: mainStyle.border }} className="text-[10px] px-2 py-1 rounded-lg font-black border font-mono tracking-tighter shadow-sm">
                        {s?.category || "一般個股"}
                      </span>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="animate-fadeIn">
                      <td colSpan="3" className="bg-slate-50/50 px-6 py-6 border-b border-slate-100 shadow-inner">
                        <div className="flex flex-col gap-6">
                          <div className="flex flex-wrap gap-4">
                            <div className="flex gap-6 bg-white px-5 py-3 rounded-2xl border border-slate-100 shadow-sm">
                              {[{ k: 'foreign', l: '外資' }, { k: 'trust', l: '投信' }, { k: 'dealer', l: '自營' }].map(inst => (
                                <div key={inst.k} className="text-center min-w-[60px]">
                                  <p className="text-[10px] text-slate-400 font-black mb-1">{inst.l}</p>
                                  <p className={`font-mono font-black text-xs ${s[inst.k] >= 0 ? 'text-red-500' : 'text-green-600'}`}>{formatK(s[inst.k])}</p>
                                </div>
                              ))}
                            </div>
                            <div className="flex gap-6 bg-slate-100/50 px-5 py-3 rounded-2xl border border-slate-200 shadow-sm">
                              <div className="text-center min-w-[60px]">
                                <p className="text-[10px] text-slate-500 font-black mb-1">融資增減</p>
                                <p className={`font-mono font-black text-xs ${s.margin?.f_change >= 0 ? 'text-red-500' : 'text-green-600'}`}>{formatK(s.margin?.f_change)}</p>
                              </div>
                              <div className="text-center min-w-[60px]">
                                <p className="text-[10px] text-slate-500 font-black mb-1">融券增減</p>
                                <p className={`font-mono font-black text-xs ${s.margin?.s_change >= 0 ? 'text-red-500' : 'text-green-600'}`}>{formatK(s.margin?.s_change)}</p>
                              </div>
                            </div>
                          </div>
                          {otherTags.length > 0 && (
                            <div className="flex flex-col gap-2 pl-2 border-l-2 border-slate-200">
                              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">更多產業屬性</span>
                              <div className="flex flex-wrap gap-2">
                                {otherTags.map(([tKey, tName]) => {
                                  const stl = TAG_THEMES[tKey];
                                  const isvaluechain = data?.sectors?.buy?.some(sector => sector.name === tName);
                                  return (
                                    <span key={tKey} style={{ backgroundColor: stl.bg, color: stl.text, borderColor: stl.border }} className="px-2 py-1 rounded-md text-[10px] font-black shadow-sm flex items-center gap-1">
                                      {isvaluechain && <span>🔥</span>}
                                      {tName}
                                    </span>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fadeIn">
      <div className="flex flex-col gap-4">
        <Table items={list.tse_b} isBuy={true} title="上市買超 (張)" />
        <Table items={list.otc_b} isBuy={true} title="上櫃買超 (張)" />
      </div>
      <div className="flex flex-col gap-4">
        <Table items={list.tse_s} isBuy={false} title="上市賣超 (張)" />
        <Table items={list.otc_s} isBuy={false} title="上櫃賣超 (張)" />
      </div>
    </div>
  );
}

// 追加貼在 src/pages/InstitutionalFundPage.jsx 的最底部

export function RadarView({ data, onScanComplete }) {
  const [activeKey, setActiveKey] = useState('steady');
  const [progress, setProgress] = useState(0);
  const [serverIsRunning, setServerIsRunning] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  useEffect(() => {
    if (data && !serverIsRunning && !isUpdating) return;
    const timer = setInterval(() => {
      fetch(`http://localhost:5000/api/radar_progress?t=${Date.now()}`)
        .then(res => res.json())
        .then(d => {
          setProgress(d.progress);
          setServerIsRunning(d.is_running);
          if (d.progress === 100 && d.is_running === false) {
            if (!data || isUpdating) onScanComplete();
            setIsUpdating(false);
            clearInterval(timer);
          }
        })
        .catch(() => clearInterval(timer));
    }, 2500);
    return () => clearInterval(timer);
  }, [data, isUpdating, serverIsRunning, onScanComplete]);

  const handleRefresh = async () => {
    if (serverIsRunning || isUpdating) return;
    setIsUpdating(true);
    setProgress(0);
    try {
      await fetch('http://localhost:5000/api/radar/refresh', { method: 'POST' });
    } catch {
      setIsUpdating(false);
    }
  };

  const isScanning = serverIsRunning || (isUpdating && progress < 100);

  return (
    <div className="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100 animate-fadeIn relative overflow-hidden">
      {isScanning && (
        <div className="absolute top-0 left-0 w-full h-1 bg-slate-100 z-10">
          <div className="h-full bg-blue-600 transition-all duration-1000 ease-in-out shadow-[0_0_8px_rgba(37,99,235,0.5)]" style={{ width: `${Math.max(progress, 2)}%` }}></div>
        </div>
      )}
      <div className="mb-6 px-5 py-3 bg-slate-50/50 rounded-2xl border border-slate-100/50 flex justify-between items-center">
        <div className="flex items-center text-slate-400 font-bold text-[11px] tracking-tight">
          <span className="mr-1.5">今日篩選率:</span>
          <span className="text-blue-600 font-black text-sm font-mono">{isScanning ? "計算中..." : (data?.stats?.hit_rate || "---")}</span>
          <span className="mx-4 opacity-20 text-slate-300">|</span>
          <span className="mr-1.5">命中數:</span>
          <span className="text-slate-700 font-black font-mono">{isScanning ? "--" : (data?.stats?.hit_count || 0)}</span>
          <span className="text-slate-400 mx-1">/</span>
          <span className="text-slate-400 font-mono">{isScanning ? "1975" : (data?.stats?.total_count || "---")}</span>
        </div>
        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 px-3 py-1 rounded-full border shadow-sm transition-all ${isScanning ? 'bg-blue-50 border-blue-100' : 'bg-white border-slate-200/50'}`}>
            <span className="relative flex h-2 w-2">
              <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${isScanning ? 'animate-ping bg-blue-400' : 'bg-emerald-400'}`}></span>
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isScanning ? 'bg-blue-500' : 'bg-emerald-500'}`}></span>
            </span>
            <span className={`text-[10px] font-black tracking-tighter ${isScanning ? 'text-blue-600' : 'text-emerald-700'}`}>{isScanning ? `實時價格掃描中 ${progress}%` : '訊號實時監控中'}</span>
          </div>
          <div className="font-mono text-[10px] text-slate-400 font-bold opacity-60">{isScanning ? "SYNCING..." : (data?.stats?.scan_time || "---")}</div>
        </div>
      </div>
      <div className="flex items-center gap-4 mb-8 overflow-x-auto pb-2">
        {[{ id: 'first_break', l: '首日突破' }, { id: 'steady', l: '縮量站穩' }, { id: 'momentum', l: '動能噴發' }].map(g => (
          <button key={g.id} onClick={() => setActiveKey(g.id)} className={`px-6 py-2 rounded-xl text-sm font-black transition-all ${activeKey === g.id ? 'bg-slate-800 text-white shadow-lg scale-105' : 'bg-slate-50 text-slate-400 hover:bg-slate-100'}`}>
            {g.l} ({isScanning ? "-" : (data?.groups?.[g.id]?.length || 0)})
          </button>
        ))}
        <button onClick={handleRefresh} disabled={isScanning} className="ml-auto flex items-center gap-1.5 text-[10px] font-black text-blue-600 hover:text-blue-700 transition-all bg-blue-50/50 hover:bg-blue-50 px-4 py-2 rounded-xl border border-blue-100 shadow-sm disabled:opacity-30">
          <svg className={`w-3 h-3 ${isScanning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          {isScanning ? '正在更新' : '刷新實時價格'}
        </button>
      </div>
      <div className={`grid grid-cols-1 md:grid-cols-2 gap-6 transition-opacity duration-500 ${isScanning && data ? 'opacity-40 pointer-events-none' : 'opacity-100'}`}>
        {!data && isScanning ? <div className="col-span-full py-40 text-center text-slate-300 font-black animate-pulse">正在進行數據掃描...</div> :
          data?.groups?.[activeKey]?.map((item, i) => (
            <div key={i} className={`bg-slate-50 rounded-[30px] p-6 transition-all hover:shadow-lg border ${item.is_limit_up ? 'border-[3px] border-red-400 shadow-[0_0_15px_-3px_rgba(248,113,113,0.2)]' : 'border-slate-100'}`}>
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-baseline gap-2">
                  <h4 className="text-2xl font-black text-slate-800 tracking-tighter">{item.name}</h4>
                  <span className="text-slate-400 text-sm font-mono opacity-60 uppercase font-bold">{item.stock_id}</span>
                  {item.state_key !== 'first_break' && item.break_count > 1 && <span className="px-1.5 py-0.5 bg-indigo-50 text-indigo-600 text-[10px] font-black rounded border border-indigo-100 leading-none">D{item.break_count}</span>}
                </div>
                <div className="flex items-center">
                  {item.is_disposition && <span className="mr-2 inline-flex items-center justify-center bg-yellow-400 text-black px-2 h-5 rounded-md text-[10px] font-black leading-none shadow-sm ring-1 ring-yellow-500/30">處置</span>}
                  <span className="bg-blue-600 text-white px-3 py-1 rounded-lg text-sm font-black tracking-tight font-mono shadow-sm">price:{item.price}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 mb-4">
                {item.chip_tag && <span className={`px-2 py-1 rounded-md text-[10px] font-black border shadow-sm transition-all ${item.chip_tag.includes('🔥') ? 'bg-orange-50 text-orange-600 border-orange-100' : item.chip_tag.includes('🔴') ? 'bg-red-50 text-red-600 border-red-100' : item.chip_tag.includes('🌊') ? 'bg-blue-50 text-blue-600 border-blue-100' : item.chip_tag.includes('💎') ? 'bg-purple-50 text-purple-600 border-purple-100' : item.chip_tag.includes('⚓') ? 'bg-indigo-50 text-indigo-600 border-indigo-100' : 'bg-white text-slate-500 border-slate-200'}`}>{item.chip_tag}</span>}
                {item.money_label && <span className="text-[12px] font-black text-purple-600 ml-1">{item.money_label}</span>}
              </div>
              <pre className="text-[12px] font-sans text-slate-600 bg-white p-5 rounded-2xl border border-slate-50 whitespace-pre-wrap leading-relaxed shadow-sm font-bold">{item.full_text}</pre>
            </div>
          ))
        }
      </div>
    </div>
  );
}

function SectorView({ data }) {
  const [expandedSector, setExpandedSector] = useState(null);
  const Row = ({ item, isBuy, rank }) => {
    const theme = TAG_THEMES[item.tag_type] || TAG_THEMES.basic;
    return (
      <React.Fragment>
        <div className="border-b border-slate-50 last:border-0">
          <div onClick={() => setExpandedSector(expandedSector === item.name ? null : item.name)} className="flex justify-between items-center py-5 hover:bg-slate-50 px-3 rounded-2xl cursor-pointer transition">
            <div className="flex gap-5 items-center">
              <span className="text-slate-200 font-black italic text-2xl w-8">{rank}.</span>
              <div>
                <div className="font-black text-xl mb-0.5" style={{ color: theme.text }}>{item?.name}</div>
                <div className="text-[11px] text-slate-400 font-bold tracking-tight opacity-70">外 {formatK(item.foreign)} / 信 {formatK(item.trust)} / 自 {formatK(item.dealer)} (張)</div>
              </div>
            </div>
            <div className={`font-black text-xl ${isBuy ? 'text-red-500' : 'text-green-600'}`}>{formatK(item.total)}</div>
          </div>
          {expandedSector === item.name && item.top_components && (
            <div className="px-14 pb-5 grid grid-cols-1 gap-1 animate-fadeIn">
              {item.top_components.map((c, idx) => (
                <div key={idx} className="flex justify-between text-xs py-2 border-l-2 border-slate-100 pl-4">
                  <span className="font-bold text-slate-600">{c.stock_name}</span>
                  <span className={`font-black ${c.total >= 0 ? 'text-red-500' : 'text-green-600'}`}>{formatK(c.total)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </React.Fragment>
    );
  };
  return (
    <div className="bg-white p-8 md:p-10 rounded-[40px] shadow-sm border grid grid-cols-1 lg:grid-cols-2 gap-20 animate-fadeIn">
      <div>
        <h3 className="text-red-500 font-black mb-8 text-xs border-b-2 border-red-50 pb-3 uppercase tracking-widest flex items-center"><span className="w-2 h-2 rounded-full bg-red-500 mr-2"></span>法人買超族群 (張)</h3>
        {data?.buy?.length > 0 ? data.buy.map((item, i) => <Row key={i} item={item} isBuy={true} rank={i + 1} />) : <p className="py-20 text-center text-slate-300 font-bold italic uppercase tracking-widest">No sector data</p>}
      </div>
      <div>
        <h3 className="text-green-600 font-black mb-8 text-xs border-b-2 border-green-50 pb-3 uppercase tracking-widest flex items-center"><span className="w-2 h-2 rounded-full bg-green-600 mr-2"></span>法人賣超族群 (張)</h3>
        {data?.sell?.length > 0 ? data.sell.map((item, i) => <Row key={i} item={item} isBuy={false} rank={i + 1} />) : <p className="py-20 text-center text-slate-300 font-bold italic uppercase tracking-widest">No sector data</p>}
      </div>
    </div>
  );
}