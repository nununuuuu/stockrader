import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import LiquidCard from '../components/LiquidCard';
import { formatBillion } from '../utils/format';

export default function SectorGroupPage({
  subTab,
  valuechainData,
  fetchMainData,
  fetchValuechainData
}) {
  return (
    <div className="animate-fadeIn">
      <div>
        {subTab === 'valuechain' && (
          <ValuechainView
            data={valuechainData}
            onUpdateComplete={() => { fetchMainData(); fetchValuechainData(); }}
          />
        )}
        {subTab === 'sector_rank' && (
          <div className="p-20 text-center text-slate-400 font-bold border-2 border-dashed border-slate-200 rounded-[40px] bg-white">
            🧩 板塊排行榜功能開發中...
          </div>
        )}
      </div>
    </div>
  );
}

// ========================================================
// 📦 物理歸位：原本死黏在 App.jsx 底部的重型視圖，在此正式安家
// ========================================================
function ValuechainView({ data, onUpdateComplete }) {
  const [valuechainProgress, setValuechainProgress] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const [selectedIndustry, setSelectedIndustry] = useState(null);
  const [isDrawerClosing, setIsDrawerClosing] = useState(false);

  const sourceData = data?.valuechain_map ? data.valuechain_map : data;
  const { resonance = [], top5 = [], others = [] } = sourceData || {};

  const isDataLoading = !data || data.status === "loading";
  const shouldPoll = isSyncing || isDataLoading;

  useEffect(() => {
    let timer;
    if (shouldPoll) {
      timer = setInterval(async () => {
        try {
          const res = await fetch("http://localhost:5000/api/valuechain_progress");
          const d = await res.json();
          setValuechainProgress(d.progress);

          if (!d.is_running) {
            setIsSyncing(false);
            clearInterval(timer); // 物理拆除計時器

            if (onUpdateComplete) {
              setTimeout(() => {
                onUpdateComplete();
              }, 1000);
            }
          }
        } catch (err) {
          console.error("熱門產業初始化輪詢失敗", err);
        }
      }, 2500); // 2.5秒探頭輪詢
    }
    return () => clearInterval(timer);
  }, [shouldPoll, onUpdateComplete]);

  const openIndustryDrawer = (industry) => {
    setIsDrawerClosing(false);
    setSelectedIndustry(industry);
  };

  const closeIndustryDrawer = () => {
    setIsDrawerClosing(true);
    setTimeout(() => {
      setSelectedIndustry(null);
      setIsDrawerClosing(false);
    }, 280);
  };

  useEffect(() => {
    if (!selectedIndustry) return undefined;

    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') closeIndustryDrawer();
    };
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [selectedIndustry]);

  const handleManualUpdate = async () => {
    if (!window.confirm("確定要更新全台股產業地圖嗎？預計需時 2 分鐘。")) return;
    setIsSyncing(true);
    setValuechainProgress(0);
    try {
      const response = await fetch("http://localhost:5000/api/admin/update_valuechain_map", { method: 'POST' });
      if (!response.ok) throw new Error("產業鏈重新載入失敗");
    } catch {
      setIsSyncing(false);
    }
  };

  if (isDataLoading && !isSyncing) {
    return (
      <div className="py-40 text-center flex flex-col items-center">
        <div className="w-10 h-10 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
        <p className="text-slate-400 font-black">資料初始化中... {valuechainProgress}%</p>
      </div>
    );
  }

  return (
    <div className="animate-fadeIn space-y-12 pb-20 relative">
      {/* 1. 多產業共振核心 */}
      {resonance?.length > 0 && (
        <section>
          <header className="mb-4 flex items-baseline gap-3">
            <h2 className="text-xl font-black text-amber-600 tracking-tighter">多產業共振核心</h2>
            <span className="text-slate-400 text-[10px] tracking-widest font-black uppercase">Resonance Hubs</span>
          </header>

          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-5">
            {resonance.map((d, i) => (
              <LiquidCard key={i} item={d} isResonance={true} />
            ))}
          </div>
        </section>
      )}

      {/* 2. 今日價量領頭羊 */}
      <section>
        <header className="mb-4 flex items-center justify-between px-2">
          <div className="flex items-baseline gap-3">
            <h2 className="text-xl font-black text-blue-900 tracking-tighter">今日價量領頭羊</h2>
            <span className="text-slate-400 text-[10px] tracking-widest font-black uppercase">Top 5 Leaders</span>
          </div>
          <button onClick={handleManualUpdate} disabled={isSyncing} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-all shadow-sm disabled:opacity-50 group">
            <svg className={`w-3 h-3 text-slate-400 group-hover:text-blue-500 ${isSyncing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            <span className="text-[10px] font-black text-slate-400 group-hover:text-slate-600 uppercase">{isSyncing ? `同步中 ${valuechainProgress}%` : '更新產業地圖'}</span>
          </button>
        </header>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-5">
          {top5?.length > 0 ? top5.map((d, i) => <LiquidCard key={i} item={d} isHero={true} onSelect={() => openIndustryDrawer(d)} />) : [1, 2, 3, 4, 5].map(i => <div key={i} className="aspect-square bg-slate-100 rounded-[24px] animate-pulse" />)}
        </div>
      </section>

      {/* 3. 全市場金流矩陣 */}
      <section>
        <header className="mb-4 flex items-baseline gap-3 opacity-50">
          <h2 className="text-sm font-black text-slate-500 uppercase">全市場金流矩陣</h2>
          <span className="text-slate-400 text-[9px] tracking-widest font-black">FULL MATRIX</span>
        </header>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {others?.map((d, i) => <LiquidCard key={i} item={d} isHero={false} onSelect={() => openIndustryDrawer(d)} />)}
        </div>
      </section>

      {/* 4. 側邊欄彈窗抽屜 (Portal Drawer) */}
      {selectedIndustry && createPortal(
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className={`absolute inset-0 bg-slate-950/20 ${isDrawerClosing ? 'valuechain-backdrop-out' : 'valuechain-backdrop-in'}`} onClick={closeIndustryDrawer}></div>
          <aside role="dialog" aria-modal="true" aria-label={`${selectedIndustry.name}產業明細`} className={`relative h-full w-full max-w-[430px] bg-white shadow-[-14px_0_34px_rgba(15,23,42,0.12)] border-l border-slate-200 flex flex-col ${isDrawerClosing ? 'valuechain-drawer-out' : 'valuechain-drawer-in'}`}>
            <header className="px-5 py-5 border-b border-slate-200 bg-white">
              <div className="flex items-start justify-between gap-4 pb-4 border-b border-slate-100">
                <div className="min-w-0">
                  <h3 className="text-xl font-black text-slate-900 leading-tight">{selectedIndustry.name}</h3>
                  <div className="flex items-center gap-2 mt-2 min-w-0">
                    <span className="shrink-0 px-1.5 py-0.5 rounded bg-orange-50 text-[10px] font-black text-orange-500">{selectedIndustry.main}</span>
                    <p className="truncate text-[11px] font-bold text-slate-400">{selectedIndustry.path}</p>
                  </div>
                </div>
                <button type="button" aria-label="關閉產業明細" onClick={closeIndustryDrawer} className="shrink-0 w-8 h-8 rounded-md border border-slate-200 text-slate-400 hover:text-slate-900 hover:bg-slate-50 font-black">×</button>
              </div>

              <div className="space-y-1.5 pt-4">
                {[
                  { l: '當日法人淨買超', v: selectedIndustry.net_inst_1d, u: '億' },
                  { l: '近 5 日法人淨買超', v: selectedIndustry.inst_net_5d, u: '億' },
                  { l: '近 20 日累計', v: selectedIndustry.inst_net_20d, u: '億' },
                ].map((row, idx) => (
                  <div key={idx} className="flex justify-between items-center text-sm leading-6">
                    <span className="font-medium text-slate-600">{row.l}</span>
                    <span className={`font-black ${row.v == null ? 'text-slate-300' : row.v >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                      {formatBillion(row.v, row.u)}
                    </span>
                  </div>
                ))}

                <div className="flex justify-between items-start gap-3 text-sm leading-6">
                  <span className="shrink-0 font-medium text-slate-600">資金停留</span>
                  <div className="text-right">
                    {(() => {
                      const historyDays = selectedIndustry.history_days || 0;
                      if (historyDays < 2) {
                        return <span className="font-black text-slate-300">歷史資料回填中</span>;
                      }
                      const streak = selectedIndustry.inflow_streak || 0;
                      const accel = selectedIndustry.accel ?? 0;
                      const isIn = streak >= 0;
                      const isUp = accel >= 0;

                      return (
                        <>
                          <span className={`font-black whitespace-nowrap ${isIn ? 'text-red-500' : 'text-emerald-600'}`}>
                            資金連續{isIn ? '流入' : '流出'} {Math.abs(streak)} 天
                          </span>
                          <span className={`ml-2 whitespace-nowrap text-[10px] font-bold ${isUp ? 'text-red-400' : 'text-emerald-500'}`}>
                            {isUp ? '↑' : '↓'} {isIn ? (isUp ? '流入加速' : '流入放緩') : (isUp ? '流出放緩' : '流出加速')}
                          </span>
                        </>
                      );
                    })()}
                  </div>
                </div>

                <div className="flex justify-between items-center text-sm leading-6">
                  <span className="font-medium text-slate-600">近 5 日漲跌</span>
                  <span className={`font-black ${selectedIndustry.change_5d == null ? 'text-slate-300' : selectedIndustry.change_5d >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                    {formatBillion(selectedIndustry.change_5d, '%')}
                  </span>
                </div>
              </div>
              <p className="text-[9px] text-slate-300 font-bold text-right mt-2">法人股數以當日收盤價估算金額</p>
            </header>

            <div className="flex-1 overflow-y-auto">
              <table className="w-full table-fixed text-sm">
                <thead className="sticky top-0 bg-white/95 backdrop-blur border-b border-slate-100 text-[11px] text-slate-400 z-10">
                  <tr>
                    <th className="w-[54px] text-left font-black pl-4 pr-1 py-3">代碼</th>
                    <th className="text-left font-black px-1 py-3">名稱</th>
                    <th className="w-[62px] text-right font-black px-1 py-3">收盤</th>
                    <th className="w-[65px] text-right font-black px-1 py-3">當日漲跌</th>
                    <th className="w-[82px] text-right font-black pl-1 pr-4 py-3">當日買超</th>
                  </tr>
                </thead>
                <tbody>
                  {(selectedIndustry.components || []).map((stock) => (
                    <tr key={stock.id} className="border-b border-slate-50 hover:bg-slate-50/80 transition-colors">
                      <td className="pl-4 pr-1 py-3 font-mono font-bold text-slate-700">{stock.id}</td>
                      <td className="px-1 py-3 min-w-0">
                        <p className="truncate font-bold text-slate-700" title={stock.name}>{stock.name}</p>
                      </td>
                      <td className="px-1 py-3 text-right font-mono text-slate-400">{Number(stock.price || 0).toLocaleString('zh-TW', { maximumFractionDigits: 2 })}</td>
                      <td className={`px-1 py-3 text-right font-black font-mono ${(stock.change || 0) >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                        {formatBillion(stock.change, '%')}
                      </td>
                      <td className="pl-1 pr-4 py-3 text-right">
                        <div className={`font-black font-mono ${stock.inst_net >= 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                          {formatBillion(stock.inst_net, '億')}
                        </div>
                        {stock.is_abnormal && (
                          <div className="mt-1 flex justify-end">
                            <span className={`px-1.5 py-0.5 border text-[9px] font-black rounded leading-none ${stock.abnormal_type === 'buy'
                                ? 'border-red-200 text-red-500 bg-red-50/50'
                                : 'border-emerald-200 text-emerald-600 bg-emerald-50/50'
                              }`}>
                              {stock.abnormal_type === 'buy' ? '異常大買' : '異常大賣'}
                            </span>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
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
