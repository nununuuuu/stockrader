import React, { useEffect, useState } from 'react';

// ==========================================
// 顏色配置區：方便你直接修改 Hex 色碼
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
      <div className="flex w-full mb-1.5 text-[10px] font-black text-slate-500 uppercase tracking-tighter">
        <div className="w-[25%] text-center">極度恐懼</div>
        <div className="w-[20%] text-center">恐懼</div>
        <div className="w-[10%] text-center">中立</div>
        <div className="w-[20%] text-center">貪婪</div>
        <div className="w-[25%] text-center">極度貪婪</div>
      </div>

      {/* 2. 🌟 核心膠囊進度條 */}
      <div className="relative h-2 w-full flex rounded-full overflow-hidden border border-slate-50">
        {segments.map((seg, i) => (
          <div key={i} style={{ width: seg.width, backgroundColor: seg.color }} className="h-full" />
        ))}
      </div>

      {/* 3. 🌟 三角形指針與數值 */}
      <div className="relative w-full h-6 mt-0.5">
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


const MarginRatioGauge = ({ ratio = 0 }) => {
  const r = parseFloat(ratio) || 0;
  const maxRange = 20;
  const percentage = Math.min(Math.max(r / maxRange, 0), 1);
  const radius = 22;
  const circumference = radius * Math.PI;
  const offset = circumference - (percentage * circumference);

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative w-24 h-14">
        <svg viewBox="0 0 50 30" className="w-full h-full">
          <path d="M 5 28 A 20 20 0 0 1 45 28" fill="none" stroke="#f1f5f9" strokeWidth="6" strokeLinecap="round" />
          <path d="M 5 28 A 20 20 0 0 1 45 28" fill="none"
            stroke={r > 15 ? "#ef4444" : r > 8 ? "#f59e0b" : "#6366f1"}
            strokeWidth="6" strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out" />
          {/* 🌟 在圓弧中心放 % 數字 */}
          <text x="50%" y="25" textAnchor="middle" fontSize="10" fontWeight="900" fill="#1e293b" className="font-mono">
            {r}%
          </text>
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

export default function App() {
  const [data, setData] = useState(null);
  const [hotMapData, setHotMapData] = useState(null);
  const [radarData, setRadarData] = useState(null);
  const [initProgress, setInitProgress] = useState({ percentage: 0, current_item: "", is_done: false });
  const [tab, setTab] = useState('radar');
  const [excludeETF, setExcludeETF] = useState(false);

  const API_BASE = "http://localhost:5000";
  const todayStr = new Date().toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).replace(/\//g, '');

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
            fetchHotMapData();
          }
        })
        .catch(err => console.error("進度輪詢失敗"));
    }, 1500);
    return () => clearInterval(progressTimer);
  }, []);

  useEffect(() => {
    if (tab === 'hot' && !hotMapData) {
      fetch(`${API_BASE}/api/hot_map`).then(res => res.json()).then(setHotMapData);
    }
  }, [tab, hotMapData]);

  const fetchMainData = () => {
    fetch(`${API_BASE}/api/data`).then(res => (res.status === 202 ? null : res.json())).then(d => { if (d) setData(d); });
  };

  const fetchRadarData = () => {
    fetch(`${API_BASE}/api/radar`).then(res => res.json()).then(setRadarData);
  };

  const fetchHotMapData = () => {
    fetch(`${API_BASE}/api/hot_map`).then(res => res.json()).then(setHotMapData);
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
            <h1 className="text-3xl font-black text-blue-900 tracking-tighter">法人資金監測</h1>
            <div className="flex items-center bg-white border border-slate-200 px-3 py-1 rounded-xl shadow-sm">
              <span className="text-[10px] font-black text-slate-400 mr-1.5 uppercase">DATA REF</span>
              <span className="text-sm font-mono font-black text-slate-600 mr-2">
                {data?.date ? `${data.date.slice(0, 4)}/${data.date.slice(4, 6)}/${data.date.slice(6, 8)}` : "----/--/--"}
              </span>

              {/* 🌟 顯示舊資料警告 */}
              {data?.stale_warnings && data.stale_warnings.length > 0 ? (
                <div className="flex gap-1">
                  {data.stale_warnings.map((msg, idx) => {
                    // 1. 提取訊息中的 8 位數日期
                    const msgDateMatch = msg.match(/\d{8}/);
                    const msgDate = msgDateMatch ? msgDateMatch[0] : null;
                    const refDate = data.date;
                    // 2. 判定顏色類型
                    let colorClass = "bg-amber-50 text-amber-500 border-amber-100"; // 預設橘黃 (未對齊)
                    if (msgDate && refDate) {
                      if (parseInt(msgDate) < parseInt(refDate)) {
                        // 資料日期早於基準日 = 過時 (紅色)
                        colorClass = "bg-red-50 text-red-500 border-red-100 animate-pulse";
                      }
                    }
                    return (
                      <span
                        key={idx}
                        className={`px-1.5 py-0.5 text-[9px] font-black rounded border ${colorClass}`}
                      >
                        {msg}
                      </span>
                    );
                  })}
                </div>
              ) : (
                <span className="px-1.5 py-0.5 bg-blue-50 text-blue-500 text-[9px] font-black rounded border border-blue-100">
                  FULL SYNCED
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 mt-3">
            <button onClick={() => setExcludeETF(!excludeETF)} className={`px-5 py-1.5 text-xs font-black rounded-full border transition shadow-sm ${excludeETF ? 'bg-orange-500 text-white border-orange-500' : 'bg-white text-slate-400 border-slate-200 hover:border-orange-300'}`}>
              {excludeETF ? '✕ 只顯示個股' : '□ 包含所有數據'}
            </button>
          </div>
        </div>
        <div className="flex bg-white border border-slate-200 rounded-2xl p-1 shadow-sm h-14 items-center overflow-x-auto">
          {[{ id: 'radar', l: '台股雷達' }, { id: 'hot', l: '熱門資金' }, { id: 'sectors', l: '族群資金' }, { id: 'total', l: '法人總計' }, { id: 'foreign', l: '外資' }, { id: 'trust', l: '投信' }, { id: 'dealer', l: '自營' }].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`px-6 h-10 rounded-xl text-sm font-black transition whitespace-nowrap ${tab === t.id ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:bg-slate-50'}`}>{t.l}</button>
          ))}
        </div>
      </div>

      {/* 🌟 決策級看板：3:3:3:3 全真實數據對齊版 🌟 */}
      <div className="grid grid-cols-12 gap-5 mb-8">

        {/* [卡片 1] 價格維度：指數與市場寬度 */}
        <div className="col-span-12 lg:col-span-3 bg-white p-5 rounded-[24px] shadow-sm border border-slate-100 flex flex-col justify-between h-[250px]">
          <div>
            <div className="text-slate-400 text-[9px] font-black uppercase tracking-widest mb-1 opacity-70">Market Price</div>
            <div className={`text-3xl font-black mb-1 ${data.taiex?.diff >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {data.taiex?.price?.toLocaleString() || "--,---"}
            </div>
            <div className={`flex items-center gap-1.5 text-xs font-black ${data.taiex?.diff >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {data.taiex ? (
                <>
                  <span>{data.taiex.diff >= 0 ? '▲' : '▼'} {Math.abs(data.taiex.diff)}</span>
                  <span className="opacity-60">({data.taiex.pct}%)</span>
                </>
              ) : <span>-- ( --% )</span>}
            </div>
            <div className="flex flex-wrap gap-2 mt-3 items-center">
              <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${data.taiex?.is_above_ma20 ? 'bg-red-50 text-red-500 border-red-100' : 'bg-green-50 text-green-600 border-green-100'}`}>MA20</span>
              <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${data.taiex?.is_above_ma60 ? 'bg-red-50 text-red-500 border-red-100' : 'bg-green-50 text-green-600 border-green-100'}`}>MA60</span>
              <span className="ml-auto text-[10px] font-black text-blue-500 bg-blue-50/50 px-2 py-0.5 rounded border border-blue-100/50">
                量比 {data.taiex?.vol_ratio ? data.taiex.vol_ratio.toFixed(2) : "--.--"}x
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

        {/* [卡片 2] 心理維度：解決溢出問題 (精算高度版) */}
        <div className="col-span-12 lg:col-span-3 bg-white p-4 rounded-[24px] shadow-sm border border-slate-100 flex flex-col h-[250px] overflow-hidden">
          <div className="text-center">
            <span className="text-slate-400 text-[9px] font-black uppercase tracking-widest opacity-60">Market Sentiment</span>
          </div>

          {/* 1. 膠囊指針：稍微上移 */}
          <div className="mt-0">
            <SentimentGauge score={data?.sentiment?.now?.score} />
          </div>

          {/* 2. 歷史對照：極限壓縮垂直間距 */}
          <div className="mt-1 flex flex-col px-1">
            {[
              { label: "昨日", d: data?.sentiment?.last },
              { label: "一週", d: data?.sentiment?.week },
              { label: "一月", d: data?.sentiment?.month }
            ].map((h, i) => (
              <div key={i} className="flex justify-between items-center py-0.5">
                <span className="text-[10px] text-slate-400 font-bold">{h.label}</span>
                <div className="flex items-center gap-2">
                  <span className={`text-[8px] font-black uppercase ${h.d?.score > 55 ? 'text-emerald-500' : h.d?.score < 45 ? 'text-red-400' : 'text-slate-400'
                    }`}>
                    {h.d?.label || "---"}
                  </span>
                  <span className="font-mono font-black text-slate-600 text-[10px] w-6 text-right">
                    {h.d?.score ?? "---"}
                  </span>
                </div>
              </div>
            ))}
          </div>


          {/* 🌟 修正點：縮小底部 VIX 區塊高度 */}
          <div className="mt-auto pt-2 border-t border-slate-100 flex justify-between items-center">
            <div className="flex flex-col">
              <span className="text-slate-400 text-[8px] font-black uppercase leading-none mb-1">VIX INDEX</span>
              <span className="text-xl font-black font-mono text-slate-700 leading-none">
                {data?.sentiment?.vix ? data.sentiment.vix.toFixed(2) : "--.--"}
              </span>
            </div>

            {data?.sentiment?.vix ? (
              <div className={`px-2 py-0.5 text-[10px] font-black rounded border ${getVixStatus(data.sentiment.vix).color}`}>
                {getVixStatus(data.sentiment.vix).label}
              </div>
            ) : (
              <div className="px-2 py-0.5 bg-slate-50 text-slate-300 text-[8px] font-black rounded border border-slate-100">N/A</div>
            )}
          </div>


          {/* 背離警示 (如果有) */}
          {data?.sentiment?.divergence && (
            <div className="text-center mt-2 animate-pulse">
              <span className="text-[9px] font-black text-orange-500 uppercase tracking-tighter">Signal Divergence</span>
            </div>
          )}
        </div>

        {/* [卡片 3] 主力維度：真實火力分佈 */}
        <div className="col-span-12 lg:col-span-3 bg-white p-5 rounded-[24px] shadow-sm border border-slate-100 flex flex-col justify-between h-[250px]">
          <div>
            <div className="text-slate-400 text-[9px] font-black uppercase tracking-widest mb-1 opacity-70">Main Force (Net)</div>
            <div className={`text-3xl font-black ${data?.summary?.total >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {data?.summary ? formatBillion(data.summary.total) : "--.--"}<span className="text-[20px] ml-0.5 opacity-40">億</span>
            </div>

            <div className="space-y-3.5 mt-4">
              {['foreign', 'trust', 'dealer'].map(k => {
                const val = data?.summary?.[k] || 0;
                const maxVal = Math.max(
                  Math.abs(data?.summary?.foreign || 0),
                  Math.abs(data?.summary?.trust || 0),
                  Math.abs(data?.summary?.dealer || 0),
                  100
                );
                const barWidth = (Math.abs(val) / maxVal) * 50;
                const isPositive = val >= 0;
                return (
                  <div key={k} className="space-y-1">
                    <div className="flex justify-between text-[9px] font-black uppercase">
                      <span className="text-slate-400">{k === 'foreign' ? '外資' : k === 'trust' ? '投信' : '自營'}</span>
                      <span className={isPositive ? 'text-red-500' : 'text-green-600'}>
                        {formatBillion(val)}
                      </span>
                    </div>
                    <div className="relative h-1.5 w-full bg-slate-50 rounded-full overflow-hidden border border-slate-100/50">
                      <div className="absolute left-1/2 top-0 w-px h-full bg-slate-200 z-10" />
                      <div
                        className={`absolute top-0 h-full transition-all duration-1000 ease-out ${isPositive ? 'bg-red-400' : 'bg-green-400'}`}
                        style={{
                          width: `${barWidth}%`,
                          left: isPositive ? '50%' : 'auto',
                          right: !isPositive ? '50%' : 'auto'
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="py-2 rounded-xl text-center border border-slate-100 bg-slate-50/80 shadow-sm transition-all mt-2">
            <span className="text-[10px] font-black tracking-wider text-slate-600 uppercase">
              {data?.signals?.inst || "Wait Sync"}
            </span>
          </div>
        </div>

        {/* [卡片 4] 槓桿維度：真實券資比指針 */}
        <div className="col-span-12 lg:col-span-3 bg-white p-5 rounded-[24px] shadow-sm border border-slate-100 flex flex-col h-[250px] overflow-hidden">
          {/* 1. 頂部標題 */}
          <div className="text-slate-400 text-[9px] font-black uppercase tracking-widest opacity-70 mb-2">
            Leverage Analysis
          </div>

          {/* 2. 🌟 中間區：左邊數據、右邊指針 */}
          <div className="flex justify-between items-center flex-1">
            {/* 左側數據堆疊 */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="w-1 h-7 bg-orange-400/80 rounded-full" />
                <div className="flex flex-col">
                  <span className="text-[10px] text-slate-400 font-black uppercase leading-none mb-0.5">融資增減</span>
                  <div className={`text-xl font-black font-mono leading-none ${data?.margin?.financing >= 0 ? 'text-red-500' : 'text-green-600'}`}>
                    {(data?.margin && data.margin.financing !== undefined) ? formatBillion(data.margin.financing) : "--.--"}
                    <span className="text-[11px] ml-0.5 opacity-40">億</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1 h-7 bg-indigo-400/80 rounded-full" />
                <div className="flex flex-col">
                  <span className="text-[10px] text-slate-400 font-black uppercase leading-none mb-0.5">融券增減</span>
                  <div className={`text-xl font-black font-mono leading-none ${data?.margin?.short_selling >= 0 ? 'text-red-500' : 'text-green-600'}`}>
                    {(data?.margin && data.margin.short_selling !== undefined) ? formatK(data.margin.short_selling) : "--"}
                    <span className="text-[11px] ml-0.5 opacity-40">張</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 右側指針 (填充空白處) */}
            <div className="pr-1">
              <MarginRatioGauge ratio={data?.margin?.ratio} />
            </div>
          </div>

          {/* 3. 🌟 底部：極度壓縮的上市櫃數據條 (不擠壓結論) */}
          <div className="mt-3 flex justify-around items-center py-1 bg-slate-50/50 rounded-lg border border-slate-100/50">
            <div className="flex flex-col items-center">
              <span className="text-[9px] text-slate-400 font-bold uppercase scale-90">上市</span>
              <span className="text-[10px] font-black font-mono text-slate-600">{data?.margin?.tse_ratio || "---"}%</span>
            </div>
            <div className="w-px h-3 bg-slate-200" />
            <div className="flex flex-col items-center">
              <span className="text-[9px] text-slate-400 font-bold uppercase scale-90">上櫃</span>
              <span className="text-[10px] font-black font-mono text-slate-600">{data?.margin?.otc_ratio || "---"}%</span>
            </div>
          </div>

          {/* 4. 結論標籤 (完全貼底) */}
          <div className={`mt-3 py-1.5 rounded-xl text-center border shadow-sm transition-all text-[10px] font-black tracking-wider uppercase
            ${data?.signals?.margin?.includes('💎') ? 'bg-indigo-50 border-indigo-200 text-indigo-600' : 'bg-slate-50 border-slate-100 text-slate-500'}`}>
            {data?.signals?.margin || "Wait Sync"}
          </div>
        </div>

      </div>

      {/* 分頁內容 */}
      <div className="transition-all duration-300">
        {tab === 'hot' && (
          <HotMapView
            data={hotMapData}
            onUpdateComplete={() => {
              fetchMainData();    
              fetchHotMapData(); 
            }}
          />
        )}
        {tab === 'radar' && <RadarView data={radarData} onScanComplete={(val) => { if (val === null) setRadarData(null); else fetchRadarData(); }} />}
        {tab === 'sectors' && <SectorView data={data?.sectors} />}
        {(tab !== 'radar' && tab !== 'sectors' && tab !== 'hot') && (
          <RankingView list={currentList} type={tab} excludeETF={excludeETF} data={data} />
        )}
      </div>
    </div>
  );
}

// ==========================================
// 排行榜：上下佈局 & 顏色過濾
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
// 雷達頁面：強化監控標籤與籌碼動向
// ==========================================
function RadarView({ data, onScanComplete }) {
  const [activeKey, setActiveKey] = useState('steady');
  const [progress, setProgress] = useState(0);
  const [serverIsRunning, setServerIsRunning] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  // 1. 核心輪詢邏輯：具備「強制拆除」功能
  useEffect(() => {
    // 🌟 第一道防線：如果資料已經回來了，且伺服器沒在跑，也沒按更新，直接不啟動輪詢
    if (data && !serverIsRunning && !isUpdating) {
      return;
    }

    const timer = setInterval(() => {
      fetch(`http://localhost:5000/api/radar_progress?t=${Date.now()}`)
        .then(res => res.json())
        .then(d => {
          // 更新本地狀態
          setProgress(d.progress);
          setServerIsRunning(d.is_running);

          // 🌟 第二道防線：精準判斷「掃描完成」的那一刻
          // 條件：進度 100% 且 伺服器回報已經停了 (is_running: false)
          if (d.progress === 100 && d.is_running === false) {
            console.log("📡 偵測到掃描已徹底結束，執行停火...");

            // 如果目前畫面上還是舊資料或沒資料，才去抓新的
            if (!data || isUpdating) {
              onScanComplete();
            }

            setIsUpdating(false);
            clearInterval(timer); // 🌟 核心：從內部物理拆除計時器
          }
        })
        .catch(err => {
          console.error("輪詢連線失敗，自動停止");
          clearInterval(timer);
        });
    }, 2500); // 頻率微調為 2.5 秒，減輕負擔

    return () => {
      console.log("🧹 清理計時器中...");
      clearInterval(timer);
    };
  }, [data, isUpdating]); // 🌟 只監控這兩個關鍵訊號

  // 2. 手動刷新按鈕
  const handleRefresh = async () => {
    if (serverIsRunning || isUpdating) return;
    setIsUpdating(true);
    setProgress(0);
    try {
      await fetch('http://localhost:5000/api/radar/refresh', { method: 'POST' });
      // 指令送出後，useEffect 會因為 isUpdating 變 true 而重新啟動輪詢
    } catch (err) {
      alert("啟動失敗");
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
            {isScanning ? "計算中..." : (data?.stats?.hit_rate || "---")}
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

        <div className="flex items-center gap-4 ">
          <div className={`flex items-center gap-2 px-3 py-1 rounded-full border shadow-sm transition-all ${isScanning ? 'bg-blue-50 border-blue-100' : 'bg-white border-slate-200/50'} `}>
            <span className="relative flex h-2 w-2">
              <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${isScanning ? 'animate-ping bg-blue-400' : 'bg-emerald-400'}`}></span>
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isScanning ? 'bg-blue-500' : 'bg-emerald-500'}`}></span>
            </span>
            {/* 🌟 修正 2：將掃描進度趴數移到狀態燈這裡，更符合直覺 */}
            <span className={`text-[10px] font-black tracking-tighter ${isScanning ? 'text-blue-600' : 'text-emerald-700'} `}>
              {isScanning ? `實時價格掃描中 ${progress}%` : '訊號實時監控中'}
            </span>
          </div>

          <div className="font-mono text-[10px] text-slate-400 font-bold opacity-60">
            {isScanning ? "SYNCING..." : (data?.stats?.scan_time || "---")}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 mb-8 overflow-x-auto pb-2">
        {[{ id: 'first_break', l: '首日突破' }, { id: 'steady', l: '縮量站穩' }, { id: 'momentum', l: '動能噴發' }].map(g => (
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
              {/* 🌟 標籤與紫圈顯示區 */}
              <div className="flex items-center gap-2 mb-4">
                {/* 1. 核心模型/共振標籤 (彩色背景按鈕) */}
                {item.chip_tag && (
                  <span className={`px-2 py-1 rounded-md text-[10px] font-black border shadow-sm transition-all
                ${item.chip_tag.includes('🔥') ? 'bg-orange-50 text-orange-600 border-orange-100' :
                      item.chip_tag.includes('🔴') ? 'bg-red-50 text-red-600 border-red-100' :
                        item.chip_tag.includes('🌊') ? 'bg-blue-50 text-blue-600 border-blue-100' :
                          item.chip_tag.includes('💎') ? 'bg-purple-50 text-purple-600 border-purple-100' :
                            item.chip_tag.includes('⚓') ? 'bg-indigo-50 text-indigo-600 border-indigo-100' :
                              'bg-white text-slate-500 border-slate-200'}`}>
                    {item.chip_tag}
                  </span>
                )}

                {/* 2. 🌟 紫圈標籤文字：資金主戰場 | 投信重倉 (純文字顯示在按鈕旁) */}
                {item.money_label && (
                  <span className="text-[12px] font-black text-purple-600 ml-1">
                    {item.money_label}
                  </span>
                )}

              </div>
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
// 族群頁面：同步顏色與自營商顯示
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

// ==========================================
// 熱門產業金流分頁組件
// ==========================================
function HotMapView({ data, onUpdateComplete }) {
  // 1. 統一狀態管理
  const [hotProgress, setHotProgress] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const [msg, setMsg] = useState("");

  const { resonance = [], top5 = [], others = [] } = data || {};

  // 2. 自動輪詢邏輯：監控後端進度
  useEffect(() => {
    let timer;
    if (isSyncing) {
      timer = setInterval(async () => {
        try {
          const res = await fetch("http://localhost:5000/api/hot_progress");
          const d = await res.json();
          setHotProgress(d.progress);

          // 當後端回報停止執行且進度達到 100
          if (!d.is_running && d.progress === 100) {
            setIsSyncing(false);
            setMsg("更新完成！正在刷新數據...");
            clearInterval(timer);

            // 💡 關鍵：呼叫父組件傳進來的刷新函數 (fetchMainData)
            if (onUpdateComplete) {
              setTimeout(() => {
                onUpdateComplete();
                setMsg("");
              }, 1000);
            }
          }
        } catch (err) {
          console.error("輪詢失敗", err);
        }
      }, 2000); // 每 2 秒問一次
    }
    return () => clearInterval(timer);
  }, [isSyncing, onUpdateComplete]);

  // 3. 手動更新處理
  const handleManualUpdate = async () => {
    if (!window.confirm("確定要更新全台股產業地圖嗎？預計需時 2 分鐘。")) return;

    setIsSyncing(true);
    setHotProgress(0);
    setMsg("正在啟動背景同步任務...");

    try {
      await fetch("http://localhost:5000/api/admin/update_industry_map", { method: 'POST' });
    } catch (err) {
      setMsg("連線失敗");
      setIsSyncing(false);
    }
  };

  // 4. 加載中狀態處理 (僅在完全沒資料且也沒在同步時顯示)
  if ((!data || data === "loading") && !isSyncing) {
    return (
      <div className="py-40 text-center flex flex-col items-center">
        <div className="w-10 h-10 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
        <p className="text-slate-400 font-black uppercase tracking-widest text-xs">數據計算中...</p>
      </div>
    );
  }

  // 子組件：液體卡片 (保持不變)
  const LiquidCard = ({ item, isResonance, isHero }) => {
    const isUp = item.change >= 0;
    const liquidColor = isUp ? '#f87171' : '#34d399';
    const textColor = isUp ? 'text-red-500' : 'text-green-600';
    const fillLevel = Math.min((item.flow || item.total_flow) * 2.0 + 12, 95);
    const encodedColor = encodeURIComponent(liquidColor);
    const waveSvg = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 20'%3E%3Cpath d='M0 10 Q100 0 200 10 T400 10 L400 20 L0 20 Z' fill='${encodedColor}'/%3E%3C/svg%3E`;

    let containerClass = "relative overflow-hidden transition-all duration-300 shadow-sm ";
  if (isResonance) {
    // 共振卡片：寬矩形，較大
    containerClass += "bg-white border-2 border-amber-400/30 rounded-[28px] resonance-pulse h-[160px] col-span-2 md:col-span-1";
  } else if (isHero) {
    // 領頭羊卡片：正方形，中等
    containerClass += "bg-white border border-slate-100 rounded-[20px] aspect-square hover:shadow-md";
  } else {
    // 矩陣卡片：正方形，小
    containerClass += "bg-white border border-slate-100 rounded-lg aspect-square p-2";
  }

    return (
      <div className={containerClass}>
        <div className="absolute bottom-0 left-0 w-full transition-all duration-[2s] ease-in-out z-0" style={{ height: `${fillLevel}%`, backgroundColor: liquidColor }}>
          <div className="absolute top-[-15px] left-0 w-[200%] h-5 animate-waveSlide" style={{ backgroundImage: `url("${waveSvg}")`, backgroundSize: '50% 100%' }}></div>
        </div>
        <div className="relative z-10 h-full flex flex-col justify-between p-3 pointer-events-none">
          <div className="flex justify-between items-start">
            <span className={`text-[9px] font-black uppercase tracking-tighter ${isResonance ? 'text-amber-600' : 'text-slate-400'}`}>{isResonance ? `Resonance` : isHero ? `Top Focus` : ''}</span>
            <span className={`text-[10px] font-black ${isHero || isResonance ? 'text-white drop-shadow-md' : textColor}`}>{isUp ? '▲' : '▼'} {Math.abs(item.change).toFixed(1)}%</span>
          </div>
          <div className="mt-auto">
            <h4 className={`${isHero || isResonance ? 'text-lg' : 'text-[10px]'} font-black text-slate-800 leading-tight`}>{item.name}</h4>
            <div className={`${isHero || isResonance ? 'text-3xl' : 'text-base'} font-black text-slate-900 tracking-tighter`}>{item.flow || item.total_flow}<span className="text-[10px] ml-0.5 opacity-40">%</span></div>
          </div>
          <div className="mt-1">
            {isResonance ? (
              <div className="flex flex-wrap gap-1">
                {item.sectors.map((s, i) => (<span key={i} className="text-[8px] bg-black/5 px-1.5 py-0.5 rounded-md text-slate-600 font-bold border border-black/5">{s}</span>))}
              </div>
            ) : <p className={`text-[9px] truncate font-bold ${isHero ? 'text-white/80' : 'text-slate-400'}`}>{item.path}</p>}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="animate-fadeIn space-y-12 pb-20 relative">

      {/* 🌟 核心：進度條顯示區 (與雷達邏輯對齊) */}
      {isSyncing && (
        <div className="sticky top-4 z-50 bg-blue-600 text-white px-6 py-3 rounded-2xl shadow-2xl border border-blue-400 flex items-center justify-between mb-8 animate-bounce">
          <div className="flex items-center gap-4">
            <div className="w-32 h-2 bg-blue-800 rounded-full overflow-hidden border border-blue-500">
              <div className="h-full bg-white transition-all duration-500" style={{ width: `${hotProgress}%` }}></div>
            </div>
            <span className="text-xs font-black font-mono">MAP SYNCING: {hotProgress}%</span>
          </div>
          <span className="text-[10px] font-black uppercase tracking-widest animate-pulse">正在解析產業價值鏈...</span>
        </div>
      )}

      {/* 1. 共振核心個股 */}
      {resonance.length > 0 && (
        <section>
          <header className="mb-4 flex items-baseline gap-3">
            <h2 className="text-xl font-black text-amber-600 tracking-tighter">多產業共振核心</h2>
            <span className="text-slate-400 text-[10px] tracking-widest font-black uppercase">Resonance Hubs</span>
          </header>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-5">
            {resonance.map((s) => <LiquidCard key={s.id} item={s} isResonance={true} />)}
          </div>
        </section>
      )}

      {/* 2. 今日領頭羊 */}
      <section>
        <header className="mb-4 flex items-baseline justify-between px-2">
          <div className="flex items-baseline gap-3">
            <h2 className="text-xl font-black text-blue-900 tracking-tighter">今日價量領頭羊</h2>
            <span className="text-slate-400 text-[10px] tracking-widest font-black uppercase">Top 5 Leaders</span>
          </div>

          <div className="flex items-center gap-3">
            {msg && <span className="text-[10px] font-bold text-amber-500 animate-pulse">{msg}</span>}
            <button
              onClick={handleManualUpdate}
              disabled={isSyncing}
              className="group flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-all shadow-sm disabled:opacity-50"
            >
              <svg className={`w-3 h-3 text-slate-400 group-hover:text-blue-500 ${isSyncing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span className="text-[10px] font-black text-slate-400 group-hover:text-slate-600 uppercase tracking-tighter">
                {isSyncing ? '同步中' : '更新產業地圖'}
              </span>
            </button>
          </div>
        </header>

        {/* 💡 掃描時顯示佔位符，掃描完自動替換為資料 */}
        {resonance.length === 0 && isSyncing ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-5">
            {[1, 2, 3, 4, 5].map(i => <div key={i} className="aspect-square bg-slate-100 rounded-[20px] animate-pulse"></div>)}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-5">
            {top5.map((d, i) => <LiquidCard key={i} item={d} isHero={true} />)}
          </div>
        )}
      </section>

      {/* 3. 全產業監測 */}
      <section>
        <header className="mb-4 flex items-baseline gap-3 opacity-50">
          <h2 className="text-sm font-black text-slate-500 uppercase">全市場金流矩陣</h2>
          <span className="text-slate-400 text-[9px] tracking-widest font-black">FULL MATRIX</span>
        </header>
        <div className="grid grid-cols-3 md:grid-cols-6 lg:grid-cols-10 gap-3">
          {others.map((d, i) => <LiquidCard key={i} item={d} isHero={false} />)}
        </div>
      </section>

      <style>{`
        @keyframes waveSlide { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
        .animate-waveSlide { animation: waveSlide 4s linear infinite; }
        @keyframes resonancePulse { 0%, 100% { border-color: rgba(245, 158, 11, 0.3); } 50% { border-color: rgba(245, 158, 11, 0.7); } }
        .resonance-pulse { animation: resonancePulse 2s infinite; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fadeIn { animation: fadeIn 0.6s ease-out forwards; }
      `}</style>
    </div>
  );
}

