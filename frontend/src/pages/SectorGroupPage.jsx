import React from 'react';

export default function SectorGroupPage({ 
  subTab, // 🌟 接收外部 Prop
  data, 
  valuechainData, 
  fetchMainData, 
  fetchValuechainData, 
  ValuechainView 
}) {
  return (
    <div className="animate-fadeIn">
      {/* 徹底拿掉原本內部的大膠囊 Tab 結構 */}
      <div>
        {subTab === 'valuechain' && (
          <ValuechainView data={valuechainData} onUpdateComplete={() => { fetchMainData(); fetchValuechainData(); }} />
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