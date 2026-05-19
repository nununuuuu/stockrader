import React, { useEffect, useState } from 'react';

// ==========================================
// 🌟 顏色配置區：方便你直接修改 Hex 色碼
// ==========================================
const TAG_THEMES = {
  electronics: { bg: "#e0f2fe", text: "#0369a1", border: "#bae6fd", label: "電子" },
  concepts: { bg: "#ffedd5", text: "#c2410c", border: "#fed7aa", label: "概念" },
  group: { bg: "#f3e8ff", text: "#7e22ce", border: "#e9d5ff", label: "集團" },
  basic: { bg: "#f1f5f9", text: "#475569", border: "#e2e8f0", label: "類別" }
};

// --- 格式化函數 ---

const formatBillion = (n) => {
  if (n === undefined || n === null) return '0.00';
  const val = Math.abs(n).toFixed(2);
  return n >= 0 ? `+${val}` : `-${val}`;
};

const formatK = (n) => {
  if (n === undefined || n === null || n === 0) return '0';
  const absN = Math.abs(n);
  let displayStr = "";
  if (absN >= 10000) {
    displayStr = (absN / 10000).toFixed(1) + " 萬";
  } else {
    displayStr = Math.round(absN).toLocaleString();
  }
  return n > 0 ? `+${displayStr}` : `-${displayStr}`;
};

export default function App() {
  const [data, setData] = useState(null);
  const [radarData, setRadarData] = useState(null);
  const [initProgress, setInitProgress] = useState({ percentage: 0, current_item: "", is_done: false });
  const [tab, setTab] = useState('radar');
  const [excludeETF, setExcludeETF] = useState(false);

  const API_BASE = "http://localhost:5000";

  useEffect(() => {
    const progressTimer = setInterval(() => {
      fetch(`${API_BASE}/api/init_progress`)
        .then(res => res.json())
        .then(d => {
          setInitProgress(d);
          if (d.is_done) {
            clearInterval(progressTimer);
            fetchMainData();
            fetchRadarData();
          }
        })
        .catch(err => console.error("進度輪詢失敗"));
    }, 1500);
    return () => clearInterval(progressTimer);
  }, []);


  const fetchMainData = () => {
    fetch(`${API_BASE}/api/data`).then(res => (res.status === 202 ? null : res.json())).then(d => { if (d) setData(d); });
  };

  const fetchRadarData = () => {
    fetch(`${API_BASE}/api/radar`).then(res => res.json()).then(setRadarData);
  };

  if (!data && !initProgress.is_done) return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50">
      <div className="w-80 h-3 bg-slate-200 rounded-full overflow-hidden mb-6 shadow-inner">
        <div className="h-full bg-blue-600 transition-all duration-700" style={{ width: `${initProgress.percentage}%` }}></div>
      </div>
      <h2 className="text-2xl font-black text-blue-900 mb-2 font-mono">同步產業地圖 {initProgress.percentage}%</h2>
      <p className="text-slate-400 font-bold animate-pulse">正在收錄：{initProgress.current_item || "準備連線..."}</p>
    </div>
  );

  if (!data) return <div className="p-20 text-center font-black animate-pulse text-xl text-slate-400 uppercase tracking-widest font-mono">資料匯總中...</div>;
  const currentList = data?.rankings?.[tab] || { tse_b: [], tse_s: [], otc_b: [], otc_s: [] };

  return (
    <div className="max-w-[1440px] mx-auto p-4 md:p-6 bg-[#f8fafc] min-h-screen font-sans text-slate-800">
      {/* 標頭與狀態區 */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-black text-blue-900 tracking-tighter flex items-center">
              台股法人資金監測
            </h1>
            {/* 🌟 修復後的緊湊日期標籤 */}
            <div className="flex items-center bg-slate-50 border border-slate-200 px-3 py-1 rounded-xl shadow-sm">
              <span className="text-[11px] font-black text-slate-400 uppercase tracking-tight mr-1.5 opacity-80">數據基準:</span>
              <span className="text-sm font-mono font-black text-slate-700">
                {data?.date ? `${data.date.slice(0, 4)}/${data.date.slice(4, 6)}/${data.date.slice(6, 8)}` : "----/--/--"}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 mt-3">
            <button onClick={() => setExcludeETF(!excludeETF)} className={`px-5 py-1.5 text-xs font-black rounded-full border transition shadow-sm ${excludeETF ? 'bg-orange-500 text-white border-orange-500' : 'bg-white text-slate-400 border-slate-200 hover:border-orange-300'}`}>
              {excludeETF ? '✕ 只顯示個股' : '□ 包含所有數據'}
            </button>
          </div>
        </div>
        <div className="flex bg-white border border-slate-200 rounded-2xl p-1 shadow-sm h-14 items-center overflow-x-auto">
          {[{ id: 'radar', l: '台股雷達' }, { id: 'sectors', l: '族群資金' }, { id: 'total', l: '法人總計' }, { id: 'foreign', l: '外資' }, { id: 'trust', l: '投信' }, { id: 'dealer', l: '自營' }].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`px-6 h-10 rounded-xl text-sm font-black transition whitespace-nowrap ${tab === t.id ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:bg-slate-50'}`}>{t.l}</button>
          ))}
        </div>
      </div>

      {/* 頂部看板區 */}
      <div className="grid grid-cols-12 gap-6 mb-10">
        <div className="col-span-12 lg:col-span-4 bg-white p-7 rounded-[35px] shadow-sm border border-slate-100 flex flex-col justify-center">
          <div className="text-slate-500 text-sm font-black mb-1 font-mono uppercase tracking-widest opacity-60">加權指數</div>
          {data.taiex ? (
            <>
              <div className={`text-4xl font-black mb-2 ${data.taiex.diff >= 0 ? 'text-red-500' : 'text-green-600'}`}>{data.taiex.price.toLocaleString()}</div>
              <div className={`flex items-center gap-2 font-black ${data.taiex.diff >= 0 ? 'text-red-500' : 'text-green-600'}`}>
                <span>{data.taiex.diff >= 0 ? '▲' : '▼'} {Math.abs(data.taiex.diff)}</span>
                <span className="text-sm">({data.taiex.pct}%)</span>
              </div>
              <div className="flex flex-wrap items-center gap-2 mt-5">
                <span className={`px-2 py-1 rounded-md text-[10px] font-bold border transition-colors ${data.taiex.is_above_ma20 ? 'bg-red-50 text-red-500 border-red-100' : 'bg-green-50 text-green-600 border-green-100'}`}>{data.taiex.is_above_ma20 ? '↑' : '↓'} MA20</span>
                <span className={`px-2 py-1 rounded-md text-[10px] font-bold border transition-colors ${data.taiex.is_above_ma60 ? 'bg-red-50 text-red-500 border-red-100' : 'bg-green-50 text-green-600 border-green-100'}`}>{data.taiex.is_above_ma60 ? '↑' : '↓'} MA60</span>
                <span className="ml-auto px-2 py-1 rounded-md text-[10px] font-bold border bg-blue-50 text-blue-600 border-blue-100 shadow-sm">量比 {data.taiex.vol_ratio?.toFixed(2) || "0.00"}x</span>
              </div>
            </>
          ) : <div className="text-slate-300">數據獲取中...</div>}
        </div>
        <div className="col-span-12 lg:col-span-8 bg-white p-8 rounded-[35px] shadow-sm border border-slate-100 flex flex-col md:flex-row justify-between items-center gap-8">
          <div><div className="text-slate-400 text-[10px] font-black uppercase mb-1 tracking-[0.2em]">三大法人買賣金額合計</div><div className={`text-5xl font-black ${data?.summary?.total >= 0 ? 'text-red-500' : 'text-green-600'}`}>{formatBillion(data?.summary?.total)} <span className="text-2xl ml-1 text-slate-400 font-bold uppercase tracking-tight">億</span></div></div>
          <div className="grid grid-cols-3 gap-8 md:gap-12 border-t md:border-t-0 md:border-l pt-8 md:pt-0 md:pl-12 text-center">{[{ k: 'foreign', l: '外資' }, { k: 'trust', l: '投信' }, { k: 'dealer', l: '自營' }].map(i => (
            <div key={i.k}><p className="text-slate-400 text-xs mb-2 font-black uppercase tracking-widest">{i.l}</p><p className={`font-black text-2xl ${data?.summary?.[i.k] >= 0 ? 'text-red-500' : 'text-green-600'}`}>{formatBillion(data?.summary?.[i.k])} <span className="text-sm font-normal">億</span></p></div>))}</div>
        </div>
      </div>

      <div className="transition-all duration-300">
        {tab === 'radar' && <RadarView data={radarData} onScanComplete={fetchRadarData} />}
        {tab === 'sectors' && <SectorView data={data?.sectors} />}
        {(tab !== 'radar' && tab !== 'sectors') && <RankingView list={currentList} type={tab} excludeETF={excludeETF}     data={data} 
/>}
      </div>
    </div>
  );
}

// ==========================================
// 🌟 排行榜：上下佈局 & 顏色過濾
// ==========================================
function RankingView({ list, type, excludeETF, data }) {
  const [expandedId, setExpandedId] = useState(null);

  const Table = ({ items, isBuy, title }) => {
    const displayItems = (items || []).filter(i => excludeETF ? !i.is_etf : true);

    return (
      <div className="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100 mb-8 overflow-hidden">
        <h3 className={`font-black mb-6 text-sm uppercase tracking-widest ${isBuy ? 'text-red-500' : 'text-green-600'} flex items-center`}>
          <span className={`w-2 h-2 rounded-full mr-2 ${isBuy ? 'bg-red-500' : 'bg-green-600'}`}></span>
          {title}
        </h3>
        <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-slate-300 font-black uppercase border-b">
            <tr><th className="pb-4 px-2">股票名稱</th><th className="text-right pb-4 px-4 font-mono">張數</th><th className="text-right pb-4 px-2">主要類別</th></tr>
          </thead>
          <tbody>
            {displayItems.slice(0, 15).map((s) => {
              const isExpanded = expandedId === s.stock_id;
              const mainTagType = Object.keys(TAG_THEMES).find(key => s.all_tags?.[key]?.trim() === s.category?.trim()) || 'basic';
              const mainStyle = TAG_THEMES[mainTagType];
              
              // 獲取其他標籤
              const otherTags = Object.entries(s.all_tags || {}).filter(([tKey, tName]) => tName && tName.trim() !== s.category?.trim() && TAG_THEMES[tKey]);

              return (
                <React.Fragment key={s.stock_id}>
                  <tr onClick={() => setExpandedId(isExpanded ? null : s.stock_id)} className={`border-b border-slate-50 last:border-0 hover:bg-slate-50 transition cursor-pointer ${isExpanded ? 'bg-slate-50' : ''}`}>
                    <td className="py-4 px-2 font-black text-slate-800 text-base">
                      {s?.stock_name} <span className="text-[10px] text-slate-400 font-mono ml-1 opacity-60 font-bold uppercase">{s?.stock_id}</span>
                    </td>
                    <td className={`text-right font-black text-lg px-4 font-mono ${isBuy ? 'text-red-500' : 'text-green-600'}`}>{formatK(s?.[type] || 0)}</td>
                    <td className="text-right px-2">
                      <span style={{ backgroundColor: mainStyle.bg, color: mainStyle.text, borderColor: mainStyle.border }} className="text-[10px] px-2 py-1 rounded-lg font-black border font-mono tracking-tighter shadow-sm">{s?.category || "一般個股"}</span>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="animate-fadeIn">
                      <td colSpan="3" className="bg-slate-50/50 px-6 py-6 border-b border-slate-100 shadow-inner">
                        <div className="flex flex-col gap-6">
                          <div className="flex w-fit gap-8 bg-white px-5 py-3 rounded-2xl border border-slate-100 shadow-sm">
                            {[{ k: 'foreign', l: '外資' }, { k: 'trust', l: '投信' }, { k: 'dealer', l: '自營' }].map(inst => (
                              <div key={inst.k} className="text-center min-w-[70px]">
                                <p className="text-[10px] text-slate-400 font-black uppercase mb-1 tracking-wider">{inst.l}</p>
                                <p className={`font-mono font-black text-sm ${s[inst.k] >= 0 ? 'text-red-500' : 'text-green-600'}`}>{formatK(s[inst.k])}</p>
                              </div>))}
                          </div>
                          {otherTags.length > 0 && (
                            <div className="flex flex-col gap-2 pl-2 border-l-2 border-slate-200">
                              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">更多產業屬性</span>
                              <div className="flex flex-wrap gap-2">
                                {otherTags.map(([tKey, tName]) => {
                                  const stl = TAG_THEMES[tKey];
                                  
                                  // 🌟 修正點：使用安全鏈 ?. 並確保 data 存在
                                  const isHot = data?.sectors?.buy?.some(sector => sector.name === tName);

                                  return (
                                    <span 
                                      key={tKey} 
                                      style={{ backgroundColor: stl.bg, color: stl.text, borderColor: stl.border }} 
                                      className={`px-2 py-1 rounded-md text-[10px] font-black shadow-sm flex items-center gap-1 `}
                                    >
                                      {isHot && <span>🔥</span>}
                                      {tName}
                                    </span>
                                  );
                                })}
                              </div>
                            </div>)}
                        </div>
                      </td>
                    </tr>)}
                </React.Fragment>);
            })}
          </tbody>
        </table>
      </div>);
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
    </div>);
}
// ==========================================
// 🌟 雷達頁面：強化監控標籤與籌碼動向
// ==========================================
function RadarView({ data, onScanComplete }) {
  const [activeKey, setActiveKey] = useState('steady');
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!data) {
      const timer = setInterval(() => {
        fetch('http://localhost:5000/api/radar_progress').then(res => res.json()).then(d => {
          setProgress(d.progress);
          if (d.progress === 100) { clearInterval(timer); onScanComplete(); }
        });
      }, 1500);
      return () => clearInterval(timer);
    }
  }, [data, onScanComplete]);

  if (!data) return (
    <div className="flex flex-col items-center justify-center py-40">
      <div className="w-64 h-2 bg-slate-100 rounded-full overflow-hidden mb-4"><div className="h-full bg-blue-600 transition-all duration-500" style={{ width: `${progress}%` }}></div></div>
      <div className="text-slate-400 font-black text-sm tracking-widest animate-pulse font-mono text-center">物理數據全場掃描中 {progress}%</div>
    </div>
  );

  return (
    <div className="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100 animate-fadeIn">
      {/* 整合後的數據狀態條 */}
      <div className="mb-6 px-5 py-3 bg-slate-50/50 rounded-2xl border border-slate-100/50 flex justify-between items-center">
        <div className="flex items-center text-slate-400 font-bold text-[11px] tracking-tight">
          <span className="mr-1">篩選率</span>
          {/* 確保 key 對應到 stats.hit_rate */}
          <span className="text-blue-600 font-black text-sm font-mono">{data?.stats?.hit_rate || "0.00%"}</span>

          <span className="mx-4 opacity-20 text-slate-300">|</span>

          <span className="mr-1">命中數</span>
          <span className="text-slate-700 font-black font-mono">{data?.stats?.hit_count}</span>
          <span className="text-slate-400 mx-1">/</span>
          <span className="text-slate-400 font-mono">{data?.stats?.total_count}</span>
        </div>

        {/* 右側：監控狀態與時間 */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 bg-white/80 rounded-full border border-slate-200/50 shadow-sm">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[10px] font-black text-emerald-700 tracking-tighter uppercase">訊號實時監控中</span>
          </div>
          <div className="font-mono text-[10px] text-slate-400 font-bold opacity-60">
            {data?.stats?.scan_time}
          </div>
        </div>
      </div>

      <div className="flex gap-4 mb-8 overflow-x-auto pb-2">
        {[{ id: 'first_break', l: '🌱 首日突破' }, { id: 'steady', l: '🛡️ 縮量站穩' }, { id: 'momentum', l: '🔥 動能噴發' }].map(g => (
          <button key={g.id} onClick={() => setActiveKey(g.id)} className={`px-6 py-2 rounded-xl text-sm font-black whitespace-nowrap transition-all ${activeKey === g.id ? 'bg-slate-800 text-white shadow-lg scale-105' : 'bg-slate-50 text-slate-400 hover:bg-slate-100'}`}>
            {g.l} ({data?.groups?.[g.id]?.length || 0})
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {data?.groups?.[activeKey]?.map((item, i) => (
          <div
            key={i}
            className={`bg-slate-50 rounded-[30px] p-6 transition-all hover:shadow-lg 
              ${item.is_limit_up
                ? 'border-[3px] border-red-400 shadow-[0_0_15px_-3px_rgba(248,113,113,0.2)]'
                : 'border border-slate-100'
              }`}
          >
            <div className="flex justify-between items-center mb-4">
              <h4 className="text-2xl font-black text-slate-800">
                {item.name}
                <span className="text-slate-400 text-sm ml-2 font-mono tracking-tighter opacity-60 uppercase font-bold">
                  {item.stock_id}

                  {/* 🌟 只有在非「首日突破」且 break_count 存在時顯示天數 */}
                  {item.state_key !== 'first_break' && item.break_count > 1 && (
                    <span className="ml-1 px-1.5 py-0.5 bg-indigo-50 text-indigo-600 text-[12px] font-black rounded border border-indigo-100 shadow-sm leading-none">
                      D{item.break_count}
                    </span>
                  )}
                </span>
              </h4>
              <div className="flex gap-2">
                {item.is_limit_up && (
                  <span className="inline-flex items-center justify-center bg-red-600 text-white px-2 h-5 rounded-md text-[10px] font-black animate-pulse leading-none">
                    漲停
                  </span>
                )}

                {item.is_disposition && (
                  <span className="inline-flex items-center justify-center bg-yellow-400 text-black px-2 h-5 rounded-md text-[10px] font-black leading-none">
                    處置股
                  </span>
                )}
                <span className="bg-blue-600 text-white px-3 py-1 rounded-lg text-sm font-black tracking-tight font-mono">price:{item.price}</span>
              </div>
            </div>
            {/* 🌟 籌碼動向顯示 */}
            {item.chip_tag && (
              <div className="mb-4">
                <span className={`px-2 py-1 rounded-md text-[10px] font-black border shadow-sm ${item.chip_tag.includes('🔴') ? 'bg-red-50 text-red-600 border-red-100' : item.chip_tag.includes('⚓') ? 'bg-purple-50 text-purple-600 border-purple-100' : 'bg-white text-slate-500 border-slate-200'}`}>
                  {item.chip_tag}
                </span>
              </div>
            )}
            <pre className="text-[12px] font-sans text-slate-600 bg-white p-5 rounded-2xl border border-slate-50 whitespace-pre-wrap leading-relaxed shadow-sm font-bold mt-4">
              {item.full_text}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}

// ==========================================
// 🌟 族群頁面：同步顏色與自營商顯示
// ==========================================
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
                <div className="text-[11px] text-slate-400 font-bold tracking-tight opacity-70">
                  外 {formatK(item.foreign)} / 信 {formatK(item.trust)} / 自 {formatK(item.dealer)} (張)
                </div>
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
                </div>))}
            </div>)}
        </div>
      </React.Fragment>);
  };

  return (
    <div className="bg-white p-8 md:p-10 rounded-[40px] shadow-sm border grid grid-cols-1 lg:grid-cols-2 gap-20 animate-fadeIn">
      <div>
        <h3 className="text-red-500 font-black mb-8 text-xs border-b-2 border-red-50 pb-3 uppercase tracking-widest flex items-center">
          <span className="w-2 h-2 rounded-full bg-red-500 mr-2"></span>法人買超族群 (張)
        </h3>
        {data?.buy?.length > 0 ? data.buy.map((item, i) => <Row key={i} item={item} isBuy={true} rank={i + 1} />) : <p className="py-20 text-center text-slate-300 font-bold italic uppercase tracking-widest">No sector data</p>}
      </div>
      <div>
        <h3 className="text-green-600 font-black mb-8 text-xs border-b-2 border-green-50 pb-3 uppercase tracking-widest flex items-center">
          <span className="w-2 h-2 rounded-full bg-green-600 mr-2"></span>法人賣超族群 (張)
        </h3>
        {data?.sell?.length > 0 ? data.sell.map((item, i) => <Row key={i} item={item} isBuy={false} rank={i + 1} />) : <p className="py-20 text-center text-slate-300 font-bold italic uppercase tracking-widest">No sector data</p>}
      </div>
    </div>
  );
}