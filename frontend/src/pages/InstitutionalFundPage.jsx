import React from 'react';

export default function InstitutionalFundPage({ 
  subTab, // 🌟 改由外部傳入，統一控制
  data, 
  radarData, 
  excludeETF, 
  fetchRadarData,
  formatBillion,
  formatK,
  SentimentGauge,
  MarginRatioGauge,
  getVixStatus,
  RadarView,
  SectorView,
  RankingView
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
            <div className={`text-3xl font-black mb-1 ${data.taiex?.diff >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {data.taiex?.price?.toLocaleString() || "--,---"}
            </div>
            <div className={`flex items-center gap-1.5 text-xs font-black ${data.taiex?.diff >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {data.taiex ? <span>{data.taiex.diff >= 0 ? '▲' : '▼'} {Math.abs(data.taiex.diff)} ({data.taiex.pct}%)</span> : <span>-- ( --% )</span>}
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

        {/* [卡片 2] Market Sentiment */}
        <div className="col-span-12 lg:col-span-3 bg-white p-4 rounded-[24px] shadow-sm border border-slate-100 flex flex-col h-[250px] overflow-hidden">
          <div className="text-center"><span className="text-slate-400 text-[9px] font-black uppercase tracking-widest opacity-60">Market Sentiment</span></div>
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
        {subTab === 'radar' && <RadarView data={radarData} onScanComplete={fetchRadarData} />}
        {subTab === 'sectors' && <SectorView data={data?.sectors} />}
        {['total', 'foreign', 'trust', 'dealer'].includes(subTab) && (
          <RankingView list={currentList} type={subTab} excludeETF={excludeETF} data={data} />
        )}
      </div>
    </div>
  );
}