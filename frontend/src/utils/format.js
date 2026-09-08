
export const formatBillion = (n, unit = '') => {
  if (n === undefined || n === null || Number.isNaN(Number(n))) return `--${unit}`;
  const val = Math.abs(n).toFixed(2);
  return n >= 0 ? `+${val}${unit}` : `-${val}${unit}`;
};

export const formatK = (n) => {
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

export const getVixStatus = (val) => {
  const v = parseFloat(val);
  if (v > 40) return { label: "恐慌", color: "bg-red-50 text-red-600 border-red-100" };
  if (v < 15) return { label: "非理性繁榮", color: "bg-orange-50 text-orange-600 border-orange-100" };
  return { label: "中性", color: "bg-emerald-50 text-emerald-600 border-emerald-100" };
};
