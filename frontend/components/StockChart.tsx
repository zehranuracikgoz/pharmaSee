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
import { chartColors } from "@/lib/theme";
import { format, parseISO } from "date-fns";

interface Props {
  data: StockPricePoint[];
  color?: string;
  approvalDates?: string[];
  height?: number;
}

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload?.length) {
    return(
      <div className="bg-surface border border-border rounded-lg px-3 py-2 text-sm shadow-sm">
        <p className="text-muted text-xs mb-1">{payload[0].payload.label}</p>
        <p className="text-text font-mono font-semibold">
          ${Number(payload[0].value).toFixed(2)}
        </p>
      </div>
    );
  }
  return null;
};
export default function StockChart({
  data,
  color = chartColors.accent,
  approvalDates = [],
  height =280,
}: Props) {
  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center text-muted text-sm bg-surface2 rounded-xl"
        style={{ height }}
      >
        No price data available
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

  const labelByDate = new Map(chartData.map((d) => [d.date, d.label]));

  // approvals on weekends/holidays snap to the next trading day in the chart
  const approvalMarkers = Array.from(
    new Set (
      approvalDates
        .map((d) =>chartData.find((p) => p.date >= d.slice(0, 10))?.date)
        .filter((d): d is string => !!d && d !== chartData[0]?.date)
    )
  );

  const prices = chartData.map((d) => d.close ?? 0).filter(Boolean);
  const minPrice=Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const padding = (maxPrice - minPrice) * 0.05;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={chartColors.border} />
        {/* ISO date as the key so FDA ReferenceLines (x = ISO date) line up; ticks show "MMM d" */}
        <XAxis
          dataKey="date"
          tickFormatter={(v: string) => labelByDate.get(v) ?? v}
          tick={{ fill: chartColors.textMuted, fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: chartColors.border }}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[minPrice - padding, maxPrice + padding]}
          tick={{ fill: chartColors.textMuted, fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => `$${v.toFixed(0)}`}
          width={50}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ stroke: chartColors.border }} />
        {approvalMarkers.map((d) => (
          <ReferenceLine
            key={d}
            x={d}
            stroke={chartColors.success}
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