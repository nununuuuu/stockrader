import React, { useEffect, useState } from 'react';
import InstitutionalFundPage from './pages/InstitutionalFundPage';
import SectorGroupPage from './pages/SectorGroupPage';
import MarketMonitorPage from './pages/MarketMonitorPage';
import { createPortal } from 'react-dom';



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
              />
            )}

            {mainTab === 'funds' && (
              <InstitutionalFundPage
                subTab={subTab}
                data={data}
                radarData={radarData}
                excludeETF={excludeETF}
                fetchRadarData={fetchRadarData}
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
      await fetch("http://localhost:5000/api/admin/update_valuechain_map", { method: 'POST' });
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
            <header className="px-5 py-5 border-b border-slate-100 bg-white">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-[11px] font-black text-slate-400 tracking-widest uppercase">{selectedIndustry.main}</p>
                  <h3 className="text-2xl font-black text-slate-900 leading-tight mt-1">{selectedIndustry.name}</h3>
                  <p className="text-xs font-bold text-slate-400 mt-1 line-clamp-2">{selectedIndustry.path}</p>
                </div>
                <button onClick={closeIndustryDrawer} className="shrink-0 w-8 h-8 rounded-lg border border-slate-200 text-slate-400 hover:text-slate-900 hover:bg-slate-50 font-black text-xl">×</button>
              </div>

              {/* 1. 保留資金力道，移除其他方塊 */}
              <div className="mt-6">
                <div className="flex justify-between items-center bg-slate-50 p-4 rounded-2xl border border-slate-100 mb-5">
                  <span className="text-sm font-black text-slate-500">資金力道</span>
                  <span className={`text-2xl font-black ${(selectedIndustry.net_force || 0) >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                    {formatSigned(selectedIndustry.net_force, '億')}
                  </span>
                </div>

                {/* 2. 新增像 Tide 一樣的產業彙整清單 */}
                <div className="space-y-3 px-1">
                  <div className="flex justify-between items-center text-sm">
                    <span className="font-bold text-slate-500">當日法人淨買超</span>
                    <span className={`font-black ${(selectedIndustry.net_force || 0) >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                      {formatSigned(selectedIndustry.net_force, '億')}
                    </span>
                  </div>

                  {/* 註：以下欄位 net_force_5d, net_force_20d, inflow_streak 需要後端 API 提供，若目前沒有可先用 placeholder 或 0 */}
                  <div className="flex justify-between items-center text-sm">
                    <span className="font-bold text-slate-500">近 5 日法人淨買超</span>
                    <span className={`font-black ${(selectedIndustry.inst_net_5d || 0) >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                      {formatSigned(selectedIndustry.inst_net_5d || 0, '億')}
                    </span>
                  </div>

                  <div className="flex justify-between items-center text-sm">
                    <span className="font-bold text-slate-500">近 20 日累計</span>
                    <span className={`font-black ${(selectedIndustry.inst_net_20d || 0) >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                      {formatSigned(selectedIndustry.inst_net_20d || 0, '億')}
                    </span>
                  </div>

                  <div className="flex justify-between items-center text-sm">
                    <span className="font-bold text-slate-500">近 5 日漲跌</span>
                    <span className={`font-black ${(selectedIndustry.change_5d || 0) >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                      {formatSigned(selectedIndustry.change_5d || 0, '%')}
                    </span>
                  </div>

                  <div className="flex justify-between items-center text-sm border-t border-slate-50 pt-2">
                    <span className="font-bold text-slate-500">資金停留</span>
                    <div className="text-right">
                      {(() => {
                        // 假設後端傳來的欄位
                        const streak = selectedIndustry.inflow_streak || 0; // 正數代表流入，負數代表流出
                        const accel = selectedIndustry.accel || 0;         // 正數代表趨勢向上(買盤強/賣盤縮)，負數代表趨勢向下

                        const isInflow = streak >= 0;
                        const isTrendUp = accel >= 0;

                        // 1. 定義主狀態文字與顏色 (流入/流出)
                        const mainText = isInflow ? "流入" : "流出";
                        const mainColor = isInflow ? "text-red-500" : "text-emerald-600";

                        // 2. 定義趨勢細節 (加速/放緩) 矩陣判斷
                        let detailText = "";
                        let detailColor = "";
                        let arrow = isTrendUp ? "↑" : "↓";

                        if (isInflow) {
                          // 處於流入狀態時
                          detailText = isTrendUp ? "流入加速" : "流入放緩";
                          detailColor = isTrendUp ? "text-red-400" : "text-emerald-400";
                        } else {
                          // 處於流出狀態時
                          detailText = isTrendUp ? "流出放緩" : "流出加速";
                          detailColor = isTrendUp ? "text-red-400" : "text-emerald-400";
                        }

                        return (
                          <>
                            <span className={`font-black ${mainColor}`}>
                              資金連續{mainText} {Math.abs(streak)} 天
                            </span>
                            <span className={`ml-2 text-[10px] font-bold ${detailColor}`}>
                              {arrow} {detailText}
                            </span>
                          </>
                        );
                      })()}
                    </div>
                  </div>
                </div>
              </div>
              <p className="text-[9px] text-slate-300 font-bold text-right mt-4 uppercase tracking-tighter">金額以最新收盤價估算</p>
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
