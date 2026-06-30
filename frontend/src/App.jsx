import React, { useEffect, useState } from 'react';
import InstitutionalFundPage from './pages/InstitutionalFundPage';
import SectorGroupPage from './pages/SectorGroupPage';
import MarketMonitorPage from './pages/MarketMonitorPage';
import { createPortal } from 'react-dom';


const TAG_THEMES = {
  electronics: { bg: "#e0f2fe", text: "#0369a1", border: "#bae6fd", label: "電子" },
  concepts: { bg: "#ffedd5", text: "#c2410c", border: "#fed7aa", label: "概念" },
  group: { bg: "#f3e8ff", text: "#7e22ce", border: "#e9d5ff", label: "集團" },
  basic: { bg: "#f1f5f9", text: "#475569", border: "#e2e8f0", label: "類別" }
};

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
    displayStr = (absN / 10000).toFixed(2) + " 萬";
  } else {
    displayStr = Math.round(absN).toLocaleString();
  }
  return n > 0 ? `+${displayStr}` : `-${displayStr}`;
};

const SentimentGauge = ({ score = 50 }) => {
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

const MarginRatioGauge = ({ ratio = 0 }) => {
  const r = parseFloat(ratio) || 0;
  const radius = 22;
  const circumference = radius * Math.PI;
  const offset = circumference - (Math.min(Math.max(r / 20, 0), 1) * circumference);
  return (
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

const getVixStatus = (val) => {
  const v = parseFloat(val);
  if (v > 40) return { label: "恐慌", color: "bg-red-50 text-red-600 border-red-100" };
  if (v < 15) return { label: "非理性繁榮", color: "bg-orange-50 text-orange-600 border-orange-100" };
  return { label: "中性", color: "bg-emerald-50 text-emerald-600 border-emerald-100" };
};

const SIDEBAR_GROUPS = [
  { id: 'funds', label: '法人資金', icon: '🏛️' },
  { id: 'sectors', label: '族群板塊', icon: '🧩' },
  { id: 'market', label: '市場監控', icon: '🔭' }
];

export default function App() {
  const [data, setData] = useState(null);
  const [valuechainData, setValuechainData] = useState(null);
  const [radarData, setRadarData] = useState(null);
  const [initProgress, setInitProgress] = useState({ percentage: 0, current_item: "", is_done: false });
  const [mainTab, setMainTab] = useState('funds'); // 一級側邊欄切換狀態
  const [subTab, setSubTab] = useState('radar');   // 🌟 二級橫向子 Tab，改由中央廚房全域管理
  const [excludeETF, setExcludeETF] = useState(false);
  const [isSidebarHovered, setIsSidebarHovered] = useState(false);

  const API_BASE = "http://localhost:5000";
  const activeGroupId = mainTab;
  const activeGroup = SIDEBAR_GROUPS.find(g => g.id === activeGroupId);

  // ========================================================
  // 🌟 定義子 Tab 切換邏輯 (getSubTabs)
  // ========================================================
  const getSubTabs = () => {
    if (mainTab === 'funds') return [
      { id: 'radar', l: '台股雷達' }, { id: 'sectors', l: '族群資金' },
      { id: 'total', l: '法人總計' }, { id: 'foreign', l: '外資' },
      { id: 'trust', l: '投信' }, { id: 'dealer', l: '自營' }
    ];
    if (mainTab === 'sectors') return [
      { id: 'valuechain', l: '熱門資金' }, { id: 'sector_rank', l: '板塊排行榜' }
    ];
    return [];
  };

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
            fetchValuechainData();
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
  const fetchValuechainData = () => {
    fetch(`${API_BASE}/api/valuechain_map`)
      .then(res => res.json())
      .then(d => {
        // 確保即使拿到的是空的結構也能塞進去，打破 !data 的判斷
        setValuechainData(d);
      });
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

  return (
    <div className="min-h-screen bg-[#f8fafc] font-sans text-slate-800 flex">
      {/* 左側邊欄 */}
      <aside
        onMouseEnter={() => setIsSidebarHovered(true)}
        onMouseLeave={() => setIsSidebarHovered(false)}
        className={`fixed left-0 top-0 h-full bg-white border-r border-slate-200 z-[100] transition-all duration-300 ease-in-out shadow-xl flex flex-col ${isSidebarHovered ? 'w-60' : 'w-[72px]'}`}
      >
        <div className="h-20 flex items-center px-5 mb-4 overflow-hidden flex-shrink-0">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex-shrink-0 flex items-center justify-center text-white font-black shadow-lg shadow-blue-200">CP</div>
          <span className={`ml-4 font-black text-blue-900 tracking-tighter whitespace-nowrap transition-opacity duration-300 ${isSidebarHovered ? 'opacity-100' : 'opacity-0'}`}>CapitalPulse</span>
        </div>
        <nav className="flex-1 px-3 space-y-3">
          {SIDEBAR_GROUPS.map((group) => (
            <button
              key={group.id}
              onClick={() => {
                setMainTab(group.id);
                if (group.id === 'funds') {
                  setSubTab('radar'); // 法人資金預設秀台股雷達
                } else if (group.id === 'sectors') {
                  setSubTab('valuechain');   // 族群板塊預設秀熱門資金
                } else {
                  setSubTab(null);
                }
              }}
              className={`w-full flex items-center gap-4 p-3 rounded-2xl transition-all relative group ${mainTab === group.id ? 'bg-blue-50 text-blue-600' : 'text-slate-400 hover:bg-slate-50 hover:text-slate-600'
                }`}
            >
              <span className={`text-2xl flex-shrink-0 transition-transform ${mainTab === group.id ? 'scale-110' : 'group-hover:scale-110'}`}>{group.icon}</span>
              <span className={`font-black text-sm whitespace-nowrap transition-opacity duration-300 ${isSidebarHovered ? 'opacity-100' : 'opacity-0'}`}>{group.label}</span>
              {mainTab === group.id && <div className="absolute left-[-12px] w-1.5 h-8 bg-blue-600 rounded-full" />}
            </button>
          ))}
        </nav>
      </aside>

      {/* 主內容區域 */}
      <main className={`flex-1 transition-all duration-300 ${isSidebarHovered ? 'pl-60' : 'pl-[72px]'}`}>
        <div className="w-full max-w-[1440px] mx-auto p-4 md:p-8">

          {/* 頂部整合標頭與方案 A 摺頁子 Tab */}
          <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center border-b border-slate-200 pb-5 mb-8 gap-4">
            <div className="flex flex-wrap items-center gap-6">
              <h1 className="text-3xl font-black text-blue-900 tracking-tighter flex items-center gap-2">
                {SIDEBAR_GROUPS.find(g => g.id === mainTab)?.label || "CapitalPulse"}
              </h1>

              {/* 完美收合的精簡子 Tab 控制器 */}
              {getSubTabs().length > 0 && (
                <div className="flex gap-1.5 bg-slate-100/90 p-1.5 rounded-2xl border border-slate-200/60 shadow-inner h-12 items-center">
                  {getSubTabs().map(t => (
                    <button
                      key={t.id}
                      onClick={() => setSubTab(t.id)}
                      // 💡 調整了 px-6 (左右內距放大)、py-2 (上下微調)、text-sm (字體放大)、rounded-xl (圓角加深)
                      className={`px-6 py-2 rounded-xl text-sm font-black transition-all duration-200 tracking-tight whitespace-nowrap select-none h-9 flex items-center justify-center ${subTab === t.id
                        ? 'bg-white text-blue-600 shadow-md transform scale-102 font-black'
                        : 'text-slate-500 hover:text-slate-800 hover:bg-white/50 font-bold'
                        }`}
                    >
                      {t.l}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center bg-white border border-slate-200 px-3 py-1 rounded-xl shadow-sm text-xs font-bold text-slate-500">
                <span className="text-[10px] text-slate-400 mr-1.5 uppercase">DATA REF</span>
                <span className="font-mono">{data?.date ? `${data.date.slice(0, 4)}/${data.date.slice(4, 6)}/${data.date.slice(6, 8)}` : "----/--/--"}</span>
              </div>
              <button onClick={() => setExcludeETF(!excludeETF)} className={`px-5 py-1.5 text-xs font-black rounded-full border transition shadow-sm ${excludeETF ? 'bg-orange-500 text-white border-orange-500' : 'bg-white text-slate-400 border-slate-200 hover:border-orange-300'}`}>
              {excludeETF ? '✕ 只顯示個股' : '□ 包含所有數據'}
              </button>
            </div>
          </div>

          {/* 頁面分流 */}
          <div className="transition-all duration-300">
            {mainTab === 'market' && <MarketMonitorPage />}

            {mainTab === 'sectors' && (
              <SectorGroupPage
                subTab={subTab}
                data={data}
                valuechainData={valuechainData}
                fetchMainData={fetchMainData}
                fetchValuechainData={fetchValuechainData}
                ValuechainView={ValuechainView}
              />
            )}

            {mainTab === 'funds' && (
              <InstitutionalFundPage
                subTab={subTab}
                data={data}
                radarData={radarData}
                excludeETF={excludeETF}
                fetchRadarData={fetchRadarData}
                formatBillion={formatBillion}
                formatK={formatK}
                SentimentGauge={SentimentGauge}
                MarginRatioGauge={MarginRatioGauge}
                getVixStatus={getVixStatus}
                RadarView={RadarView}
                SectorView={SectorView}
                RankingView={RankingView}
              />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

// ==========================================
// 核心組件還原區（原本寫在 App 下方的元件們）
// ==========================================
function RankingView({ list, type, excludeETF, data }) {
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
            <tr><th className="pb-4 px-2">股票名稱</th><th className="text-right pb-4 px-4 font-mono">張數</th><th className="text-right pb-4 px-2">主要類別</th></tr>
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
                    <td className="py-4 px-2 font-black text-slate-800 text-base">{s?.stock_name} <span className="text-[10px] text-slate-400 font-mono ml-1 opacity-60 font-bold uppercase">{s?.stock_id}</span></td>
                    <td className={`text-right font-black text-lg px-4 font-mono ${isBuy ? 'text-red-500' : 'text-green-600'}`}>{formatK(s?.[type] || 0)}</td>
                    <td className="text-right px-2"><span style={{ backgroundColor: mainStyle.bg, color: mainStyle.text, borderColor: mainStyle.border }} className="text-[10px] px-2 py-1 rounded-lg font-black border font-mono tracking-tighter shadow-sm">{s?.category || "一般個股"}</span></td>
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
                                  return <span key={tKey} style={{ backgroundColor: stl.bg, color: stl.text, borderColor: stl.border }} className="px-2 py-1 rounded-md text-[10px] font-black shadow-sm flex items-center gap-1">{isvaluechain && <span>🔥</span>}{tName}</span>;
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

function RadarView({ data, onScanComplete }) {
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

function ValuechainView({ data, onUpdateComplete }) {
  // 1. 統一狀態管理
  const [valuechainProgress, setValuechainProgress] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const [msg, setMsg] = useState("");
  const [selectedIndustry, setSelectedIndustry] = useState(null);
  const [isDrawerClosing, setIsDrawerClosing] = useState(false);
  const sourceData = data?.valuechain_map ? data.valuechain_map : data;

  const { resonance = [], top5 = [], others = [] } = sourceData || {};
  // 🌟 核心修正：聰明的自動輪詢機制
  const isDataLoading = !data || data.status === "loading";

  // 💡 修正 2：只有在明確是 "loading" 狀態且還沒同步完時才輪詢
  const shouldPoll = isSyncing || isDataLoading;

  useEffect(() => {
    let timer;
    if (shouldPoll) {
      timer = setInterval(async () => {
        try {
          const res = await fetch("http://localhost:5000/api/valuechain_progress");
          const d = await res.json();
          setValuechainProgress(d.progress);

          // 判斷是否需要刷新前端畫面：
          if (!d.is_running) {
            setIsSyncing(false);
            setMsg("數據已就緒！正在自動刷新...");
            clearInterval(timer); // 物理拆除計時器

            if (onUpdateComplete) {
              setTimeout(() => {
                onUpdateComplete();
                setMsg("");
              }, 1000);
            }
          }
        } catch (err) {
          console.error("熱門產業初始化輪詢失敗", err);
        }
      }, 2500); // 2.5秒探頭問一次，溫柔不造成後端負擔
    }
    return () => clearInterval(timer);
  }, [shouldPoll, onUpdateComplete]);

  // 3. 手動更新處理 (保持原本的確認彈窗不變)
  const handleManualUpdate = async () => {
    if (!window.confirm("確定要更新全台股產業地圖嗎？預計需時 2 分鐘。")) return;
    setIsSyncing(true);
    setValuechainProgress(0);
    setMsg("正在啟動背景同步任務...");
    try {
      await fetch("http://localhost:5000/api/admin/update_valuechain", { method: 'POST' });
    } catch {
      setIsSyncing(false);
    }
  };

  // 4. 加載中狀態處理：加入即時輪詢進度提示，讓體驗更棒
  if (isDataLoading && !isSyncing) {
    return (
      <div className="py-40 text-center flex flex-col items-center">
        <div className="w-10 h-10 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
        <p className="text-slate-400 font-black">資料初始化中... {valuechainProgress}%</p>
      </div>
    );
  }

  const formatSigned = (value, unit = '') => {
    const num = Number(value || 0);
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}${unit}`;
  };

  const openIndustryDrawer = (industry) => {
    setIsDrawerClosing(false);
    setSelectedIndustry(industry);
  };

  const closeIndustryDrawer = () => {
    setIsDrawerClosing(true);
    setTimeout(() => {
      setSelectedIndustry(null);
      setIsDrawerClosing(false);
    }, 220);
  };

  const LiquidCard = ({ item, isResonance, isHero, onSelect }) => {
    const isUp = item.change >= 0;
    const netValue = isResonance ? (item.flow || item.total_flow) : (item.flow || item.total_flow || 0);
    const isNetIn = item.is_net_in ?? (netValue >= 0); // 相容後端的多空標記

    const threshold = isResonance ? 1.5 : isHero ? 5.0 : 2.0;
    const isStrong = Math.abs(netValue) >= threshold;

    let waveColor = '#f1f5f9';
    if (isNetIn) {
      waveColor = isStrong ? '#f87171' : '#FDB4B4'; // 🔥 深紅（強進攻）/ 淺紅（弱吸籌）
    } else {
      waveColor = isStrong ? '#10b981' : '#63E9AA'; // ❄️ 深綠（強提款）/ 淺綠（弱調節）
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
                <span className="text-sm font-medium text-slate-400 ml-1.5 tracking-normal">
                  {item.id || item.code}
                </span>
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
  };

  return (
    <div className="animate-fadeIn space-y-12 pb-20 relative">
      {resonance?.length > 0 && (
        <section>
          <header className="mb-4 flex items-baseline gap-3">
            <h2 className="text-xl font-black text-amber-600 tracking-tighter">多產業共振核心</h2>
            <span className="text-slate-400 text-[10px] tracking-widest font-black uppercase">Resonance Hubs</span>
          </header>

          {resonance && resonance.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-5">
              {resonance.map((d, i) => (
                <LiquidCard key={i} item={d} isResonance={true} />
              ))}
            </div>
          ) : (
            <div className="bg-white/60 border border-dashed border-slate-200 rounded-[28px] p-10 text-center text-xs font-bold text-slate-400 tracking-wide shadow-sm">
              今日市場資金集中於單一板塊，暫無跨產業共振個股
            </div>
          )}
        </section>
      )}
      <section>
        <header className="mb-4 flex items-center justify-between px-2">
          <div className="flex items-baseline gap-3"><h2 className="text-xl font-black text-blue-900 tracking-tighter">今日價量領頭羊</h2><span className="text-slate-400 text-[10px] tracking-widest font-black uppercase">Top 5 Leaders</span></div>
          <button onClick={handleManualUpdate} disabled={isSyncing} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-all shadow-sm disabled:opacity-50 group">
            <svg className={`w-3 h-3 text-slate-400 group-hover:text-blue-500 ${isSyncing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            <span className="text-[10px] font-black text-slate-400 group-hover:text-slate-600 uppercase">{isSyncing ? `同步中 ${valuechainProgress}%` : '更新產業地圖'}</span>
          </button>
        </header>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-5">
          {top5?.length > 0 ? top5.map((d, i) => <LiquidCard key={i} item={d} isHero={true} onSelect={() => openIndustryDrawer(d)} />) : [1, 2, 3, 4, 5].map(i => <div key={i} className="aspect-square bg-slate-100 rounded-[24px] animate-pulse" />)}
        </div>
      </section>
      <section>
        <header className="mb-4 flex items-baseline gap-3 opacity-50"><h2 className="text-sm font-black text-slate-500 uppercase">全市場金流矩陣</h2><span className="text-slate-400 text-[9px] tracking-widest font-black">FULL MATRIX</span></header>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">{others?.map((d, i) => <LiquidCard key={i} item={d} isHero={false} onSelect={() => openIndustryDrawer(d)} />)}</div>
      </section>
      {selectedIndustry && createPortal(
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className={`absolute inset-0 bg-slate-950/20 ${isDrawerClosing ? 'valuechain-backdrop-out' : 'valuechain-backdrop-in'}`} onClick={closeIndustryDrawer}></div>
          <aside className={`relative h-full w-full max-w-[410px] bg-white shadow-[-14px_0_34px_rgba(15,23,42,0.12)] border-l border-slate-200 flex flex-col ${isDrawerClosing ? 'valuechain-drawer-out' : 'valuechain-drawer-in'}`}>
            <header className="px-5 py-4 border-b border-slate-100 bg-white">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-[11px] font-black text-slate-400 tracking-widest">{selectedIndustry.main}</p>
                  <h3 className="text-xl font-black text-slate-900 leading-tight mt-1">{selectedIndustry.name}</h3>
                  <p className="text-xs font-bold text-slate-400 mt-1 line-clamp-2">{selectedIndustry.path}</p>
                </div>
                <button onClick={closeIndustryDrawer} className="shrink-0 w-8 h-8 rounded-lg border border-slate-200 text-slate-400 hover:text-slate-900 hover:bg-slate-50 font-black">×</button>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-4">
                <div className="rounded-md bg-slate-50/80 p-2.5 border border-slate-100">
                  <p className="text-[10px] font-black text-slate-400">金流占比</p>
                  <p className="text-base font-black text-slate-900">{Number(selectedIndustry.flow || 0).toFixed(2)}%</p>
                </div>
                <div className="rounded-md bg-slate-50/80 p-2.5 border border-slate-100">
                  <p className="text-[10px] font-black text-slate-400">平均漲跌</p>
                  <p className={`text-base font-black ${(selectedIndustry.change || 0) >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>{formatSigned(selectedIndustry.change, '%')}</p>
                </div>
                <div className="rounded-md bg-slate-50/80 p-2.5 border border-slate-100">
                  <p className="text-[10px] font-black text-slate-400">資金力道</p>
                  <p className={`text-base font-black ${(selectedIndustry.net_force || 0) >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>{formatSigned(selectedIndustry.net_force, '億')}</p>
                </div>
              </div>
            </header>
            <div className="flex-1 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white/95 backdrop-blur border-b border-slate-100 text-[11px] text-slate-400">
                  <tr>
                    <th className="text-left font-black px-5 py-3">代碼 / 名稱</th>
                    <th className="text-right font-black px-3 py-3">成交額</th>
                    <th className="text-right font-black px-3 py-3">漲跌</th>
                    <th className="text-right font-black px-5 py-3">資金</th>
                  </tr>
                </thead>
                <tbody>
                  {(selectedIndustry.components || []).map((stock) => (
                    <tr key={stock.id} className="border-b border-slate-50 hover:bg-slate-50/80">
                      <td className="px-5 py-3">
                        <p className="font-black text-slate-900">{stock.name}</p>
                        <p className="text-[11px] font-bold text-slate-400">{stock.id}</p>
                      </td>
                      <td className="px-3 py-3 text-right font-bold text-slate-500">{Number(stock.amount || 0).toFixed(2)}億</td>
                      <td className={`px-3 py-3 text-right font-black ${(stock.change || 0) >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>{formatSigned(stock.change, '%')}</td>
                      <td className={`px-5 py-3 text-right font-black ${(stock.net_force || 0) >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>{formatSigned(stock.net_force, '億')}</td>
                    </tr>
                  ))}
                  {(!selectedIndustry.components || selectedIndustry.components.length === 0) && (
                    <tr>
                      <td colSpan="4" className="px-5 py-16 text-center text-xs font-black text-slate-300">暫無產業內個股資料</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </aside>
        </div>,
        document.body
      )}
    </div>
  );
}
