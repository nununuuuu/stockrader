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

const SentimentGauge = ({ score = 50 }) => {
  const s = Math.min(Math.max(score, 0), 100);

  // 級距與配色對應
  const segments = [
    { width: '25%', color: "#fca5a5", label: "極度恐懼", eng: "EXTREME FEAR" },
    { width: '20%', color: "#fecaca", label: "恐懼", eng: "FEAR" },
    { width: '10%', color: "#e2e8f0", label: "中立", eng: "NEUTRAL" },
    { width: '20%', color: "#bbf7d0", label: "貪婪", eng: "GREED" },
    { width: '25%', color: "#86efac", label: "極度貪婪", eng: "EXTREME GREED" }
  ];

  // 判定目前狀態文字
  const getStatus = (val) => {
    if (val <= 25) return segments[0];
    if (val <= 45) return segments[1];
    if (val <= 55) return segments[2];
    if (val <= 75) return segments[3];
    return segments[4];
  };
  const current = getStatus(s);

  return (
    <div className="w-full px-2 py-4">
      {/* 1. 頂部標籤文字區：解決字體跑出問題 */}
      <div className="flex w-full mb-3 text-[9px] font-black text-slate-500 uppercase tracking-tighter">
        <div className="w-[25%] text-center">極度恐懼</div>
        <div className="w-[20%] text-center">恐懼</div>
        <div className="w-[10%] text-center">中立</div>
        <div className="w-[20%] text-center">貪婪</div>
        <div className="w-[25%] text-center">極度貪婪</div>
      </div>

      {/* 2. 🌟 核心膠囊進度條 */}
      <div className="relative h-4 w-full flex rounded-full overflow-hidden shadow-inner border border-slate-100">
        {segments.map((seg, i) => (
          <div key={i} style={{ width: seg.width, backgroundColor: seg.color }} className="h-full" />
        ))}
      </div>

      {/* 3. 🌟 三角形指針與數值 */}
      <div className="relative w-full h-8 mt-1">
        {/* 動態位移容器 */}
        <div
          className="absolute transition-all duration-1000 ease-out flex flex-col items-center"
          style={{ left: `${s}%`, transform: 'translateX(-50%)' }}
        >
          {/* 向上三角形指針 */}
          <div className="w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-b-[7px] border-b-slate-600"></div>
          <div className="text-xl font-black font-mono text-slate-600 leading-none mt-1">{s}</div>
        </div>
      </div>
    </div>
  );
};

const getVixStatus = (val) => {
  const v = parseFloat(val);
  if (v > 40) return { label: "恐慌", color: "bg-red-50 text-red-600 border-red-100" };
  if (v < 15) return { label: "非理性繁榮", color: "bg-orange-50 text-orange-600 border-orange-100" };
  return { label: "中性", color: "bg-emerald-50 text-emerald-600 border-emerald-100" };
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

      {/* 🌟 旗艦版：四維決策矩陣 (修正補完版) 🌟 */}
      <div className="grid grid-cols-12 gap-5 mb-8">
        
        {/* [卡片 1] 價格維度：補回量比 */}
        <div className="col-span-12 lg:col-span-3 bg-white p-5 rounded-[24px] shadow-sm border border-slate-100 flex flex-col justify-between h-[230px]">
          <div>
            <div className="text-slate-400 text-[9px] font-black uppercase tracking-widest mb-1 opacity-70">Market Price</div>
            <div className={`text-3xl font-black mb-1 ${data.taiex.diff >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {data.taiex.price.toLocaleString()}
            </div>
            <div className={`flex items-center gap-1.5 text-xs font-black ${data.taiex.diff >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              <span>{data.taiex.diff >= 0 ? '▲' : '▼'} {Math.abs(data.taiex.diff)}</span>
              <span className="opacity-60">({data.taiex.pct}%)</span>
            </div>
            {/* 🌟 補回量比顯示 */}
            <div className="flex flex-wrap gap-2 mt-3 items-center">
              <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${data.taiex.is_above_ma20 ? 'bg-red-50 text-red-500 border-red-100' : 'bg-green-50 text-green-600 border-green-100'}`}>MA20</span>
              <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${data.taiex.is_above_ma60 ? 'bg-red-50 text-red-500 border-red-100' : 'bg-green-50 text-green-600 border-green-100'}`}>MA60</span>
              <span className="ml-auto text-[10px] font-black text-blue-500 bg-blue-50/50 px-2 py-0.5 rounded border border-blue-100/50">量比 {data.taiex.vol_ratio?.toFixed(2)}x</span>
            </div>
          </div>
          
          <div className="space-y-1.5">
            <div className="flex justify-between text-[9px] font-black text-slate-400 uppercase">
               <span className="text-red-500">上漲 {data?.breadth?.up || 0}</span>
               <span className="text-green-600">下跌 {data?.breadth?.down || 0}</span>
            </div>
            <div className="h-1.5 w-full bg-slate-50 rounded-full flex overflow-hidden border border-slate-100">
               <div className="bg-red-400" style={{ width: `${(data?.breadth?.up / (data?.breadth?.up + data?.breadth?.down || 1)) * 100}%` }}></div>
               <div className="bg-green-400" style={{ width: `${(data?.breadth?.down / (data?.breadth?.up + data?.breadth?.down || 1)) * 100}%` }}></div>
            </div>
          </div>
        </div>

        {/* [卡片 2] 心理維度 (維持原樣) */}
        <div className="col-span-12 lg:col-span-3 bg-white p-5 rounded-[24px] shadow-sm border border-slate-100 flex flex-col justify-between h-[230px]">
          <div className="text-slate-400 text-[9px] font-black uppercase tracking-widest text-center opacity-70">Sentiment</div>
          <SentimentGauge score={data?.sentiment?.now?.score} />
          <div className="space-y-1 px-1">
            {[{ l: "昨日", d: data?.sentiment?.last }, { l: "一週前", d: data?.sentiment?.week }, { l: "一個月前", d: data?.sentiment?.month }].map((h, i) => (
              <div key={i} className="flex justify-between items-center text-[9px] font-bold">
                <span className="text-slate-400">{h.l}</span>
                <span className={h.d?.score > 55 ? 'text-emerald-500' : h.d?.score < 45 ? 'text-red-400' : 'text-slate-400'}>{h.d?.score || "--"}</span>
              </div>
            ))}
          </div>
          <div className="flex justify-between items-center pt-2 border-t border-slate-50">
             <span className="text-[12px] font-black text-slate-400">VIX {data?.sentiment?.vix?.toFixed(2)}</span>
             {(() => {
                const status = getVixStatus(data?.sentiment?.vix);
                return <div className={`px-1.5 py-0.5 text-[8px] font-black rounded border ${status.color}`}>{status.label}</div>;
             })()}
          </div>
        </div>

        {/* [卡片 3] 力量維度：補回自營商 */}
        <div className="col-span-12 lg:col-span-3 bg-white p-5 rounded-[24px] shadow-sm border border-slate-100 flex flex-col justify-between h-[230px]">
          <div>
            <div className="text-slate-400 text-[9px] font-black uppercase tracking-widest mb-1 opacity-70">Main Force</div>
            <div className={`text-3xl font-black ${data?.summary?.total >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {formatBillion(data?.summary?.total)}<span className="text-lg ml-1 text-slate-300">億</span>
            </div>
            <div className="grid grid-cols-3 gap-1.5 mt-3">
               {['foreign', 'trust', 'dealer'].map(k => (
                 <div key={k} className="bg-slate-50 p-1.5 rounded-lg border border-slate-100/50 text-center">
                   <div className="text-slate-400 text-[8px] font-black uppercase mb-0.5">{k === 'foreign' ? '外資' : k === 'trust' ? '投信' : '自營'}</div>
                   <div className={`text-[10px] font-bold font-mono ${data?.summary?.[k] >= 0 ? 'text-red-500' : 'text-green-600'}`}>{formatBillion(data?.summary?.[k])}</div>
                 </div>
               ))}
            </div>
          </div>
          <div className="bg-slate-900 text-white py-2 rounded-xl text-center shadow-md">
            <span className="text-[10px] font-black tracking-wider animate-pulse">{data?.signals?.inst || "買盤觀察中"}</span>
          </div>
        </div>

        {/* [卡片 4] 槓桿維度：補回券資比 */}
        <div className="col-span-12 lg:col-span-3 bg-white p-5 rounded-[24px] shadow-sm border border-slate-100 flex flex-col justify-between h-[230px]">
          <div>
            <div className="flex justify-between items-start">
              <div className="text-slate-400 text-[9px] font-black uppercase tracking-widest opacity-70">Retail Leverage</div>
              <div className="bg-slate-50 px-2 py-1 rounded-md border border-slate-100 text-right">
                <div className="text-[8px] text-slate-400 font-bold leading-none">券資比</div>
                <div className="text-xs font-black font-mono text-slate-700">{data?.margin?.ratio || "12.4"}%</div>
              </div>
            </div>
            <div className="space-y-3 mt-2">
              <div>
                <div className="text-slate-400 text-[9px] font-black mb-0.5">融資增減</div>
                <div className={`text-2xl font-black font-mono ${data?.margin?.financing >= 0 ? 'text-red-500' : 'text-green-600'}`}>
                  {formatBillion(data?.margin?.financing)}<span className="text-xs ml-0.5 opacity-40">億</span>
                </div>
              </div>
              <div>
                <div className="text-slate-400 text-[9px] font-black mb-0.5">融券增減</div>
                <div className={`text-2xl font-black font-mono ${data?.margin?.short_selling >= 0 ? 'text-red-500' : 'text-green-600'}`}>
                  {formatK(data?.margin?.short_selling)}<span className="text-xs ml-0.5 opacity-40">張</span>
                </div>
              </div>
            </div>
          </div>
          <div className={`py-2 rounded-xl text-center border shadow-sm ${data?.signals?.margin?.includes('💎') ? 'bg-blue-50 border-blue-100 text-blue-600' : 'bg-slate-50 border-slate-100 text-slate-600'}`}>
            <span className="text-[10px] font-black tracking-wider">{data?.signals?.margin || "槓桿穩定"}</span>
          </div>
        </div>

      </div>

      {/* 分頁內容 */}
      <div className="transition-all duration-300">
        {tab === 'radar' && <RadarView data={radarData} onScanComplete={(val) => { if (val === null) setRadarData(null); else fetchRadarData(); }} />}
        {tab === 'sectors' && <SectorView data={data?.sectors} />}
        {(tab !== 'radar' && tab !== 'sectors') && <RankingView list={currentList} type={tab} excludeETF={excludeETF} data={data} />}
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
                          {/* 上層：籌碼雙卡 (大戶 vs 散戶) */}
                          <div className="flex flex-wrap gap-4">
                            {/* 法人卡 */}
                            <div className="flex gap-6 bg-white px-5 py-3 rounded-2xl border border-slate-100 shadow-sm">
                              {[{ k: 'foreign', l: '外資' }, { k: 'trust', l: '投信' }, { k: 'dealer', l: '自營' }].map(inst => (
                                <div key={inst.k} className="text-center min-w-[60px]">
                                  <p className="text-[10px] text-slate-400 font-black mb-1">{inst.l}</p>
                                  <p className={`font-mono font-black text-xs ${s[inst.k] >= 0 ? 'text-red-500' : 'text-green-600'}`}>{formatK(s[inst.k])}</p>
                                </div>
                              ))}
                            </div>

                            {/* 🌟 信用卡 (融資券) */}
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
  const [serverIsRunning, setServerIsRunning] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  // 1. 監聽後端進度
  useEffect(() => {
    // 🌟 關鍵修正點：如果已經有資料，且伺服器沒有在運作，就「不要」啟動計時器
    if (data && !serverIsRunning && progress === 100 && !isUpdating) {
      return;
    }

    let lastRunningState = false;

    const timer = setInterval(() => {
      fetch(`http://localhost:5000/api/radar_progress?t=${Date.now()}`)
        .then(res => res.json())
        .then(d => {
          setProgress(d.progress);
          setServerIsRunning(d.is_running);

          // 如果後端從「運行中」轉為「停止」，且進度滿 100
          if (lastRunningState === true && d.is_running === false && d.progress === 100) {
            onScanComplete();
            setIsUpdating(false);
            // 🌟 這裡很重要：清除目前這個計時器，停止瘋狂請求
            clearInterval(timer);
          }

          // 初次載入判定
          if (!d.is_running && d.progress === 100 && !data) {
            onScanComplete();
            clearInterval(timer); // 停止輪詢
          }

          lastRunningState = d.is_running;
        })
        .catch(err => {
          console.error("輪詢失敗");
          clearInterval(timer); // 發生連線錯誤也停止，避免刷屏
        });
    }, 2000); // 這裡維持 2 秒一次，但有了上面的停止邏輯，跑完就不會再跑了

    return () => clearInterval(timer); // 組件卸載時清除
  }, [data, onScanComplete, isUpdating]); // 🌟 加入 isUpdating 作為依賴，點擊刷新時會重啟此 Effect

  // 2. 手動刷新按鈕行為
  const handleRefresh = async () => {
    if (serverIsRunning || isUpdating) return;
    setIsUpdating(true); // 這會觸發上面的 useEffect 重新啟動輪詢
    setProgress(0);

    try {
      await fetch('http://localhost:5000/api/radar/refresh', { method: 'POST' });
    } catch (err) {
      setIsUpdating(false);
    }
  };


  // 🌟 修正後的掃描狀態判斷：只要後端在跑，或是我們手動點了更新，都算掃描中
  const isScanning = serverIsRunning || (isUpdating && progress < 100);

  return (
    <div className="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100 animate-fadeIn relative overflow-hidden">

      {/* 頂部線性進度條 */}
      {isScanning && (
        <div className="absolute top-0 left-0 w-full h-1 bg-slate-100 z-10">
          <div
            className="h-full bg-blue-600 transition-all duration-1000 ease-in-out shadow-[0_0_8px_rgba(37,99,235,0.5)]"
            style={{ width: `${Math.max(progress, 2)}%` }}
          ></div>
        </div>
      )}

      {/* 數據狀態條 */}
      <div className="mb-6 px-5 py-3 bg-slate-50/50 rounded-2xl border border-slate-100/50 flex justify-between items-center">
        <div className="flex items-center text-slate-400 font-bold text-[11px] tracking-tight">
          <span className="mr-1.5">今日篩選率:</span>
          {/* 🌟 修正 1：掃描中不再顯示進度趴數，改顯示預設文字 */}
          <span className="text-blue-600 font-black text-sm font-mono">
            {isScanning ? "計算中..." : (data?.stats?.hit_rate || "0.00%")}
          </span>

          <span className="mx-4 opacity-20 text-slate-300">|</span>

          <span className="mr-1.5">命中數:</span>
          <span className="text-slate-700 font-black font-mono">
            {isScanning ? "--" : (data?.stats?.hit_count || 0)}
          </span>
          <span className="text-slate-400 mx-1">/</span>
          <span className="text-slate-400 font-mono">
            {isScanning ? "1975" : (data?.stats?.total_count || "---")}
          </span>
        </div>

        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 px-3 py-1 rounded-full border shadow-sm transition-all ${isScanning ? 'bg-blue-50 border-blue-100' : 'bg-white border-slate-200/50'}`}>
            <span className="relative flex h-2 w-2">
              <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${isScanning ? 'animate-ping bg-blue-400' : 'bg-emerald-400'}`}></span>
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isScanning ? 'bg-blue-500' : 'bg-emerald-500'}`}></span>
            </span>
            {/* 🌟 修正 2：將掃描進度趴數移到狀態燈這裡，更符合直覺 */}
            <span className={`text-[10px] font-black tracking-tighter ${isScanning ? 'text-blue-600' : 'text-emerald-700'}`}>
              {isScanning ? `實時價格掃描中 ${progress}%` : '訊號實時監控中'}
            </span>
          </div>

          <div className="font-mono text-[10px] text-slate-400 font-bold opacity-60">
            {isScanning ? "SYNCING..." : (data?.stats?.scan_time || "---")}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 mb-8 overflow-x-auto pb-2">
        {[{ id: 'first_break', l: '🌱 首日突破' }, { id: 'steady', l: '🛡️ 縮量站穩' }, { id: 'momentum', l: '🔥 動能噴發' }].map(g => (
          <button
            key={g.id}
            onClick={() => setActiveKey(g.id)}
            className={`px-6 py-2 rounded-xl text-sm font-black transition-all ${activeKey === g.id ? 'bg-slate-800 text-white shadow-lg scale-105' : 'bg-slate-50 text-slate-400 hover:bg-slate-100'}`}
          >
            {g.l} ({isScanning ? "-" : (data?.groups?.[g.id]?.length || 0)})
          </button>
        ))}

        <button
          onClick={handleRefresh}
          disabled={isScanning}
          className="ml-auto flex items-center gap-1.5 text-[10px] font-black text-blue-600 hover:text-blue-700 transition-all bg-blue-50/50 hover:bg-blue-50 px-4 py-2 rounded-xl border border-blue-100 shadow-sm disabled:opacity-30"
        >
          <svg className={`w-3 h-3 ${isScanning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {isScanning ? '正在更新' : '刷新實時價格'}
        </button>
      </div>

      {/* 資料清單：如果是第一次載入(完全沒資料)，才顯示大的 Loading；如果是手動刷新，則讓舊資料變淡顯示 */}
      <div className={`grid grid-cols-1 md:grid-cols-2 gap-6 transition-opacity duration-500 ${isScanning && data ? 'opacity-40 pointer-events-none' : 'opacity-100'}`}>
        {!data && isScanning ? (
          <div className="col-span-full py-40 text-center text-slate-300 font-black animate-pulse">
            正在進行數據掃描...
          </div>
        ) : (
          data?.groups?.[activeKey]?.map((item, i) => (
            <div
              key={i}
              className={`bg-slate-50 rounded-[30px] p-6 transition-all hover:shadow-lg border 
                ${item.is_limit_up
                  ? 'border-[3px] border-red-400 shadow-[0_0_15px_-3px_rgba(248,113,113,0.2)]'
                  : 'border-slate-100'
                }`}
            >
              <div className="flex justify-between items-start mb-4">
                {/* 左側：名稱、代號、天數 */}
                <div className="flex items-baseline gap-2">
                  <h4 className="text-2xl font-black text-slate-800 tracking-tighter">{item.name}</h4>
                  <span className="text-slate-400 text-sm font-mono opacity-60 uppercase font-bold">{item.stock_id}</span>

                  {item.state_key !== 'first_break' && item.break_count > 1 && (
                    <span className="px-1.5 py-0.5 bg-indigo-50 text-indigo-600 text-[10px] font-black rounded border border-indigo-100 leading-none">
                      D{item.break_count}
                    </span>
                  )}
                </div>

                {/* 右側：狀態區 (處置標記移到現價左邊) */}
                <div className="flex items-center">
                  {/* 🌟 處置標籤：黃底黑字，移到現價左邊 */}
                  {item.is_disposition && (
                    <span className="mr-2 inline-flex items-center justify-center bg-yellow-400 text-black px-2 h-5 rounded-md text-[10px] font-black leading-none shadow-sm ring-1 ring-yellow-500/30">
                      處置
                    </span>
                  )}

                  {/* 現價標籤 */}
                  <span className="bg-blue-600 text-white px-3 py-1 rounded-lg text-sm font-black tracking-tight font-mono shadow-sm">
                    price:{item.price}
                  </span>
                </div>
              </div>

              {/* 🌟 籌碼與 V3.0 特殊標籤顯示區 (這裡移除了「漲停鎖死」標籤) */}
              {item.chip_tag && (
                <div className="flex flex-wrap gap-2 mb-4">
                  <span className={`px-2 py-1 rounded-md text-[10px] font-black border shadow-sm transition-all
                    ${item.chip_tag.includes('🔴') ? 'bg-red-50 text-red-600 border-red-100' :
                      item.chip_tag.includes('🌊') ? 'bg-blue-50 text-blue-600 border-blue-100' :
                        item.chip_tag.includes('💎') ? 'bg-purple-50 text-purple-600 border-purple-100' :
                          item.chip_tag.includes('⚓') ? 'bg-indigo-50 text-indigo-600 border-indigo-100' :
                            'bg-white text-slate-500 border-slate-200'}`}>
                    {item.chip_tag}
                  </span>
                </div>
              )}
              {/* 實戰診斷與計畫文字 */}
              <pre className="text-[12px] font-sans text-slate-600 bg-white p-5 rounded-2xl border border-slate-50 whitespace-pre-wrap leading-relaxed shadow-sm font-bold">
                {item.full_text}
              </pre>
            </div>
          ))
        )}
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