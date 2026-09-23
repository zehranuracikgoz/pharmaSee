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
      <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm">
        <p className="text-gray-400 text-xs mb-1">{label}</p>
        <p className="text-white font-mono font-semibold">
          ${Number(payload[0].value).toFixed(2)}
        </p>
      </div>
    );
  }
  return null;
};
export default function StockChart({
  data,
  color = "#818cf8",
  approvalDates = [],
  height =280,
}: Props) {
  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center text-gray-500 text-sm bg-gray-800/40 rounded-xl"
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
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis
          dataKey="label"
          tick={{ fill: "#6b7280", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "#374151" }}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[minPrice - padding, maxPrice + padding]}
          tick={{ fill: "#6b7280", fontSize: 11 }}
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