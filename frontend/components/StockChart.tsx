"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine ,
} from "recharts";
import type { StockPricePoint } from "@/lib/api";
import { format, parseISO } from "date-fns";

interface Props {
  data: StockPricePoint[];
  color?: string;
  approvalDates?: string[];
  height?: number;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload?.length) {
    return(
      <div className="bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm shadow-sm">
        <p className="text-slate-400 text-xs mb-1">{label}</p>
        <p className="text-slate-900 font-mono font-semibold">
          ${Number(payload[0].value).toFixed(2)}
        </p>
      </div>
    );
  }
  return null;
};
export default function StockChart({
  data,
  color = "#2563eb",
  approvalDates = [],
  height =280,
}: Props) {
  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center text-slate-400 text-sm bg-slate-100 rounded-xl"
        style={{ height }}
      >
        Fiyat verisi bulunamadı
      </div>
    );
  }

  const chartData = data.map((d) => ({
    date: d.price_date.slice(0, 10),
    close: d.close,
    label: (() => {
      try {
        return format(parseISO(d.price_date.slice(0, 10)), "MMM d");
      } catch {
        return d.price_date.slice(0, 10);
      }
    })(),
  }));

  const prices = chartData.map((d) => d.close ?? 0).filter(Boolean);
  const minPrice=Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const padding = (maxPrice - minPrice) * 0.05;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="label"
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "#cbd5e1" }}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[minPrice - padding, maxPrice + padding]}
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => `$${v.toFixed(0)}`}
          width={50}
        />
        <Tooltip content={<CustomTooltip />} />
        {approvalDates.map((d) => (
          <ReferenceLine
            key={d}
            x={d.slice(0, 10)}
            stroke = "#f59e0b"
            strokeDasharray="4 2"
            strokeWidth={1.5}
          />
        ))}
        <Line
          type="monotone"
          dataKey="close"
          stroke={color}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: color }}
        />
      </LineChart>
    </ResponsiveContainer>
    
  );
}