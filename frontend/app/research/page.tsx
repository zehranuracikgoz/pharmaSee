"use client";

import { ReactNode, useEffect, useState } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  ErrorBar,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle } from "lucide-react";
import { chartColors } from "@/lib/theme";
import { loadResearch, Research, ScatterPoint, Strategy } from "@/lib/research";

const ORIG_COLOR = chartColors.accent;
const EFFICACY_COLOR = chartColors.warning;

// formatting

const pct = (v: number | null | undefined, digits = 2) =>
  v == null ? "-" : `${v >= 0 ? "+" : "-"}${Math.abs(v * 100).toFixed(digits)}%`;
const pValue = (p: number | null, digits = 2) =>
  p == null ? "-" : p < 0.001 ? "< 0.001" : p.toFixed(digits);
const isSig = (p: number | null | undefined) => p != null && p < 0.05;
const dayLabel = (d: number) => (d > 0 ? `+${d}` : `${d}`);
const STEPS = [0.0025, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1];

// round the axis ends to a clean step so ticks read 0.5%, 1.0% instead of 0.8%, 1.5%
function niceAxis(values: number[]) {
  const lo = Math.min(...values, 0);
  const hi = Math.max(...values, 0);
  const step = STEPS.find((s) => (hi - lo) / s <= 7) ?? 0.1;
  const start = Math.floor(lo / step + 1e-9) * step;
  const end = Math.ceil(hi / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let t = start; t <= end + step / 2; t += step) ticks.push(Math.round(t / step) * step);
  const digits = step >= 0.01 ? 0 : step >= 0.005 ? 1 : 2;
  return { domain: [start, end] as [number, number], ticks, format: (v: number) => `${(v * 100).toFixed(digits)}%` };
}
const TICK = { fill: chartColors.textMuted, fontSize: 11 };
const DAY_TICKS = [-10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10];
const legendText = (value: string) => <span style={{ color: chartColors.textMuted, fontSize: 12 }}>{value}</span>;

// small building blocks

function Section({ title, subtitle, meaning, children }: {
  title: string;
  subtitle?: string;
  meaning: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="card">
      <div className="card-header flex-col items-start gap-0.5">
        <h2 className="font-semibold text-text">{title}</h2>
        {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
      </div>
      <div className="card-body space-y-4">
        {children}
        <div className="rounded-lg bg-surface2 px-4 py-3">
          <div className="stat-label mb-1">What this means</div>
          <p className="text-sm text-text/90 leading-relaxed">{meaning}</p>
        </div>
      </div>
    </section>
  );
}

function ChartBox({ children }: { children: ReactNode }) {
  return <div className="h-72 sm:h-80 w-full">{children}</div>;
}

function TipBox({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div className="bg-surface border border-border rounded-lg px-3 py-2 text-xs shadow-sm space-y-1">
      <p className="text-muted">{title}</p>
      {rows.map(([label, value]) => (
        <p key={label} className="flex justify-between gap-4">
          <span className="text-muted">{label}</span>
          <span className="text-text font-mono">{value}</span>
        </p>
      ))}
    </div>
  );
}

const ci = (lo: number, hi: number) => `${pct(lo)} to ${pct(hi)}`;

// headline tiles

function Tile({ label, value, text }: { label: string; value: string; text: string }) {
  return (
    <div className="card p-4 flex flex-col gap-1.5">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <p className="text-sm text-muted leading-snug">{text}</p>
    </div>
  );
}

function Tiles({ data }: { data: Research }) {
  const all = data.windows.find((w) => w.key === "all")!.stats["CAR[0,+1]"];
  const large = data.windows.find((w) => w.key === "large_cap")!;
  const largeStat = large.stats["CAR[0,+1]"];
  const buy = data.strategies[data.strategies.length - 1];
  const sig = (p: number | null) => (isSig(p) ? "significant" : "not significant");
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Tile
        label="Approval day + next day"
        value={pct(all.mean)}
        text={`abnormal return over the approval day and the next (p = ${pValue(all.p)}, n = ${all.n})`}
      />
      <Tile
        label="Large caps"
        value={isSig(largeStat.p) ? "Measurable reaction" : "No measurable reaction"}
        text={`${pct(largeStat.mean)} over the same two days for ${large.tickers.join(", ")} (p = ${pValue(largeStat.p)}, n = ${largeStat.n})`}
      />
      <Tile
        label="Buying after the news"
        value={pct(buy.abnormal.mean)}
        text={`${buy.abnormal.mean < 0 ? "trailed" : "beat"} XBI over ${buy.days_held} days, entering at the ${buy.buy} (${sig(buy.abnormal.p)}, p = ${pValue(buy.abnormal.p)}, n = ${buy.n})`}
      />
    </div>
  );
}

// daily abnormal return bars

function DailyChart({ data }: { data: Research }) {
  const rows = data.days.map((day, i) => ({
    day,
    mean: data.daily_ar.mean[i],
    lo: data.daily_ar.lo[i],
    hi: data.daily_ar.hi[i],
    err: data.daily_ar.mean[i] - data.daily_ar.lo[i],
  }));
  const y = niceAxis([...data.daily_ar.lo, ...data.daily_ar.hi]);
  return (
    <ChartBox>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.border} vertical={false} />
          <XAxis dataKey="day" ticks={DAY_TICKS} tickFormatter={dayLabel} tick={TICK} tickLine={false}
                 axisLine={{ stroke: chartColors.border }} />
          <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={y.format} tick={TICK} tickLine={false}
                 axisLine={false} width={56} />
          <ReferenceLine y={0} stroke={chartColors.textMuted} />
          <Tooltip
            cursor={{ fill: chartColors.border, fillOpacity: 0.4 }}
            content={({ active, payload }: any) =>
              active && payload?.length ? (
                <TipBox
                  title={`Day ${dayLabel(payload[0].payload.day)}`}
                  rows={[
                    ["Average", pct(payload[0].payload.mean)],
                    ["95% interval", ci(payload[0].payload.lo, payload[0].payload.hi)],
                  ]}
                />
              ) : null
            }
          />
          <Bar dataKey="mean" isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.day} fill={r.day === 0 || r.day === 1 ? chartColors.accent : chartColors.barMuted} />
            ))}
            <ErrorBar dataKey="err" width={4} stroke={chartColors.text} strokeWidth={1.25} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartBox>
  );
}

function dailyMeaning(data: Research) {
  const { days, daily_ar: d } = data;
  const at = (day: number) => days.indexOf(day);
  const clear = days.filter((_, i) => d.lo[i] > 0 || d.hi[i] < 0);
  const list = clear.map((day) => `${dayLabel(day)} (${pct(d.mean[at(day)])})`).join(" and ");
  return (
    <>
      On the approval day itself stocks moved {pct(d.mean[at(0)])} on average beyond what the biotech sector (
      {data.settings.market}) explains, and on the next day {pct(d.mean[at(1)])}.{" "}
      {clear.length === 0
        ? "No single day is clearly different from zero."
        : `Only day${clear.length > 1 ? "s" : ""} ${list} ${clear.length > 1 ? "are" : "is"} clearly away from zero (the 95% interval excludes it)${clear.length <= 2 ? "; with 21 days, about one such false alarm is expected by chance" : ""}.`}{" "}
      Approvals are often announced after the market closes, which would explain why the reaction shows up on
      day +1 rather than day 0.
    </>
  );
}

// cumulative abnormal return

function CarChart({ data }: { data: Research }) {
  const rows = data.days.map((day, i) => ({
    day,
    mean: data.car.all.mean[i],
    lo: data.car.all.lo[i],
    hi: data.car.all.hi[i],
    band: [data.car.all.lo[i], data.car.all.hi[i]],
    adjusted: data.car.all_market_adjusted[i],
  }));
  const y = niceAxis([...data.car.all.lo, ...data.car.all.hi, ...data.car.all_market_adjusted]);
  return (
    <ChartBox>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.border} />
          <XAxis dataKey="day" ticks={DAY_TICKS} tickFormatter={dayLabel} tick={TICK} tickLine={false}
                 axisLine={{ stroke: chartColors.border }} />
          <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={y.format} tick={TICK} tickLine={false}
                 axisLine={false} width={56} />
          <ReferenceLine y={0} stroke={chartColors.textMuted} />
          <ReferenceLine x={0} stroke={chartColors.textMuted} strokeDasharray="2 3" />
          <Tooltip
            cursor={{ stroke: chartColors.border }}
            content={({ active, payload }: any) =>
              active && payload?.length ? (
                <TipBox
                  title={`Day ${dayLabel(payload[0].payload.day)}`}
                  rows={[
                    ["Market model", pct(payload[0].payload.mean)],
                    ["95% band", ci(payload[0].payload.lo, payload[0].payload.hi)],
                    ["Market-adjusted", pct(payload[0].payload.adjusted)],
                  ]}
                />
              ) : null
            }
          />
          <Legend formatter={legendText} />
          <Area dataKey="band" name="95% confidence band" stroke={chartColors.accent} strokeOpacity={0.5}
                strokeWidth={1} fill={chartColors.accent} fillOpacity={0.22} isAnimationActive={false} />
          <Line dataKey="mean" name={`Market model (n=${data.car.all.n})`} stroke={chartColors.accent}
                strokeWidth={2.5} dot={false} isAnimationActive={false} />
          <Line dataKey="adjusted" name="Market-adjusted (beta = 1)" stroke={chartColors.text} strokeWidth={1.5}
                strokeDasharray="5 4" dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartBox>
  );
}

function carMeaning(data: Research) {
  const car = data.car.all;
  const last = car.mean.length - 1;
  const outside = car.lo.filter((lo, i) => lo > 0 || car.hi[i] < 0).length;
  const two = data.windows.find((w) => w.key === "all")!.stats["CAR[0,+1]"];
  return (
    <>
      Added up over the window, the average stock ends {Math.abs(car.mean[last] * 100).toFixed(2)}%{" "}
      {car.mean[last] >= 0 ? "above" : "below"} what {data.settings.market} explains. The visible jump on days 0 to +1 ({pct(two.mean)}, p ={" "}
      {pValue(two.p)}) {isSig(two.p) ? "is statistically significant" : "is not statistically significant"}, but
      much of it fades over the following days. The shaded 95% band is wide (it carries the noise of the days before): it
      excludes zero on {outside} of {data.days.length} days, so the real average could be smaller, or close to
      nothing. The dashed line is a
      simpler check that treats every stock as moving one-for-one with {data.settings.market}; it tells a similar
      story.
    </>
  );
}

// original approvals vs new indications

function TypeChart({ data }: { data: Research }) {
  const { ORIG: o, EFFICACY: e } = data.car;
  const rows = data.days.map((day, i) => ({
    day,
    om: o.mean[i], olo: o.lo[i], ohi: o.hi[i], oband: [o.lo[i], o.hi[i]],
    em: e.mean[i], elo: e.lo[i], ehi: e.hi[i], eband: [e.lo[i], e.hi[i]],
  }));
  const y = niceAxis([...o.lo, ...o.hi, ...e.lo, ...e.hi]);
  return (
    <ChartBox>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.border} />
          <XAxis dataKey="day" ticks={DAY_TICKS} tickFormatter={dayLabel} tick={TICK} tickLine={false}
                 axisLine={{ stroke: chartColors.border }} />
          <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={y.format} tick={TICK} tickLine={false}
                 axisLine={false} width={56} />
          <ReferenceLine y={0} stroke={chartColors.textMuted} />
          <ReferenceLine x={0} stroke={chartColors.textMuted} strokeDasharray="2 3" />
          <Tooltip
            cursor={{ stroke: chartColors.border }}
            content={({ active, payload }: any) =>
              active && payload?.length ? (
                <TipBox
                  title={`Day ${dayLabel(payload[0].payload.day)}`}
                  rows={[
                    [`Original (n=${o.n})`, pct(payload[0].payload.om)],
                    ["  95% band", ci(payload[0].payload.olo, payload[0].payload.ohi)],
                    [`New indication (n=${e.n})`, pct(payload[0].payload.em)],
                    ["  95% band", ci(payload[0].payload.elo, payload[0].payload.ehi)],
                  ]}
                />
              ) : null
            }
          />
          <Legend formatter={legendText} />
          <Area dataKey="oband" legendType="none" stroke="none" fill={ORIG_COLOR} fillOpacity={0.2}
                isAnimationActive={false} />
          <Area dataKey="eband" legendType="none" stroke="none" fill={EFFICACY_COLOR} fillOpacity={0.15}
                isAnimationActive={false} />
          <Line dataKey="om" name={`Original approvals (n=${o.n})`} stroke={ORIG_COLOR} strokeWidth={2.5}
                dot={false} isAnimationActive={false} />
          <Line dataKey="em" name={`New indications (n=${e.n})`} stroke={EFFICACY_COLOR} strokeWidth={2.5}
                dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartBox>
  );
}

function typeMeaning(data: Research) {
  const stat = (key: string) => data.windows.find((w) => w.key === key)!.stats["CAR[0,+1]"];
  const o = stat("ORIG");
  const e = stat("EFFICACY");
  const i = data.days.indexOf(1);
  const overlap = data.car.ORIG.lo[i] <= data.car.EFFICACY.hi[i] && data.car.EFFICACY.lo[i] <= data.car.ORIG.hi[i];
  return (
    <>
      Original approvals (n = {o.n}) gained {pct(o.mean)} over days 0 to +1 (p = {pValue(o.p)}), new indications
      (n = {e.n}) {pct(e.mean)} (p = {pValue(e.p)}). {overlap
        ? "The two bands overlap, so this data cannot tell the two types apart."
        : "The two bands do not overlap on day +1."}{" "}
      Original approvals are the rarer event, so their band is much wider.
    </>
  );
}

// strategies

function StrategyTick({ x, y, payload, strategies }: any) {
  const s: Strategy | undefined = strategies.find((st: Strategy) => st.key === payload.value);
  const lines: string[] = [];
  for (const word of (s?.name ?? "").split(" ")) {
    const last = lines[lines.length - 1];
    if (last && (last + " " + word).length <= 14) lines[lines.length - 1] = `${last} ${word}`;
    else lines.push(word);
  }
  return (
    <text x={x} y={y} textAnchor="middle" fill={chartColors.textMuted} fontSize={11}>
      <tspan x={x} dy="1em" fill={chartColors.text} fontWeight={600}>{payload.value}</tspan>
      {lines.map((line) => <tspan key={line} x={x} dy="1.25em">{line}</tspan>)}
    </text>
  );
}

function StrategyChart({ data }: { data: Research }) {
  const rows = data.strategies.map((s) => ({
    key: s.key, mean: s.abnormal.mean, err: s.abnormal.mean - s.abnormal.lo, s,
  }));
  const y = niceAxis(data.strategies.flatMap((s) => [s.abnormal.lo, s.abnormal.hi]));
  return (
    <ChartBox>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.border} vertical={false} />
          <XAxis dataKey="key" interval={0} height={70} tickLine={false} axisLine={{ stroke: chartColors.border }}
                 tick={<StrategyTick strategies={data.strategies} />} />
          <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={y.format} tick={TICK} tickLine={false}
                 axisLine={false} width={56} />
          <ReferenceLine y={0} stroke={chartColors.textMuted} />
          <Tooltip
            cursor={{ fill: chartColors.border, fillOpacity: 0.4 }}
            content={({ active, payload }: any) => {
              if (!active || !payload?.length) return null;
              const s: Strategy = payload[0].payload.s;
              return (
                <TipBox
                  title={`${s.key}: ${s.name}`}
                  rows={[
                    ["Abnormal return", pct(s.abnormal.mean)],
                    ["95% interval", ci(s.abnormal.lo, s.abnormal.hi)],
                    ["Trades up", `${(s.abnormal.hit_rate * 100).toFixed(0)}%`],
                    ["p-value", pValue(s.abnormal.p)],
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="mean" fill={chartColors.accent} maxBarSize={72} isAnimationActive={false}>
            <ErrorBar dataKey="err" width={5} stroke={chartColors.text} strokeWidth={1.25} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartBox>
  );
}

function StrategyTable({ data }: { data: Research }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm min-w-[640px]">
        <thead>
          <tr className="text-left stat-label">
            <th className="py-2 pr-3 font-medium">Strategy</th>
            <th className="py-2 px-3 font-medium">Buy / sell</th>
            <th className="py-2 px-3 font-medium text-right">n</th>
            <th className="py-2 px-3 font-medium text-right">Raw</th>
            <th className="py-2 px-3 font-medium text-right">XBI</th>
            <th className="py-2 px-3 font-medium text-right">Abnormal</th>
            <th className="py-2 px-3 font-medium text-right">Trades up</th>
            <th className="py-2 pl-3 font-medium text-right">p</th>
          </tr>
        </thead>
        <tbody>
          {data.strategies.map((s) => (
            <tr key={s.key} className="border-t border-border">
              <td className="py-2 pr-3 text-text">{s.key}: {s.name}</td>
              <td className="py-2 px-3 text-muted">{s.buy} to {s.sell}</td>
              <td className="py-2 px-3 text-right font-mono text-muted">{s.n}</td>
              <td className="py-2 px-3 text-right font-mono">{pct(s.raw)}</td>
              <td className="py-2 px-3 text-right font-mono">{pct(s.xbi)}</td>
              <td className="py-2 px-3 text-right font-mono text-text">{pct(s.abnormal.mean)}</td>
              <td className="py-2 px-3 text-right font-mono">{(s.abnormal.hit_rate * 100).toFixed(0)}%</td>
              <td className={`py-2 pl-3 text-right font-mono ${isSig(s.abnormal.p) ? "text-accent font-semibold" : "text-muted"}`}>
                {pValue(s.abnormal.p)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function strategyMeaning(data: Research) {
  const sig = data.strategies.filter((s) => isSig(s.abnormal.p));
  const c = data.strategies[data.strategies.length - 1];
  return (
    <>
      Each trade is one approval, in and out at closing prices. "Abnormal" is the gain after removing what{" "}
      {data.settings.market} explains. {sig.length === 0
        ? "None of the three strategies beats the sector by a statistically significant margin."
        : `${sig.map((s) => s.key).join(" and ")} ${sig.length > 1 ? "are" : "is"} statistically significant.`}{" "}
      Buying after the news ({c.key}) made {pct(c.raw)} on its own, but the sector made {pct(c.xbi)} over the
      same days; only {(c.abnormal.hit_rate * 100).toFixed(0)}% of those trades beat their expected return. A
      0.10% round-trip cost would lower every bar by 0.10 points.
    </>
  );
}

// run-up vs reaction

function ScatterTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p: ScatterPoint = payload[0].payload;
  return (
    <TipBox
      title={`${p.ticker} · ${p.date}`}
      rows={[
        ["Type", p.kind === "ORIG" ? "Original approval" : "New indication"],
        ["Run-up (days -10 to -1)", pct(p.runup)],
        ["After (days +2 to +10)", pct(p.after)],
      ]}
    />
  );
}

function ScatterPlot({ data }: { data: Research }) {
  const { points, regression: reg } = data.scatter;
  const orig = points.filter((p) => p.kind === "ORIG");
  const eff = points.filter((p) => p.kind === "EFFICACY");
  const xs = points.map((p) => p.runup);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const ax = niceAxis(xs);
  const ay = niceAxis(points.map((p) => p.after));
  return (
    <ChartBox>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.border} />
          <XAxis type="number" dataKey="runup" name="Run-up" domain={ax.domain} ticks={ax.ticks}
                 tickFormatter={ax.format} tick={TICK} tickLine={false}
                 axisLine={{ stroke: chartColors.border }}
                 label={{ value: "Run-up before approval (days -10 to -1)", position: "insideBottom", offset: -12,
                          fill: chartColors.textMuted, fontSize: 11 }} />
          <YAxis type="number" dataKey="after" name="After" domain={ay.domain} ticks={ay.ticks}
                 tickFormatter={ay.format} tick={TICK} tickLine={false} axisLine={false} width={50} />
          <ReferenceLine x={0} stroke={chartColors.textMuted} />
          <ReferenceLine y={0} stroke={chartColors.textMuted} />
          <ReferenceLine
            segment={[
              { x: x0, y: reg.intercept + reg.slope * x0 },
              { x: x1, y: reg.intercept + reg.slope * x1 },
            ]}
            stroke={chartColors.text} strokeDasharray="6 4" strokeWidth={1.5} ifOverflow="visible"
          />
          <Tooltip content={<ScatterTip />} cursor={{ strokeDasharray: "3 3", stroke: chartColors.border }} />
          <Legend verticalAlign="top" formatter={legendText} />
          <Scatter name={`Original approvals (n=${orig.length})`} data={orig} fill={ORIG_COLOR}
                   stroke={chartColors.surface} isAnimationActive={false} />
          <Scatter name={`New indications (n=${eff.length})`} data={eff} fill={EFFICACY_COLOR}
                   stroke={chartColors.surface} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartBox>
  );
}

function scatterMeaning(data: Research) {
  const reg = data.scatter.regression;
  const evidence = isSig(reg.p) && reg.slope < 0;
  return (
    <>
      "Sell the news" would mean stocks that ran up the most before approval give the gains back afterwards, so
      the dots would slope downward. The fitted line (dashed) has a slope of {reg.slope.toFixed(2)}, with p ={" "}
      {pValue(reg.p)} and R² = {reg.r2.toFixed(3)} (n = {reg.n}).{" "}
      {evidence
        ? "That is some evidence for a pullback, but it needs more events to trust."
        : "In this data the size of the run-up says almost nothing about what happens next."}
      {reg.clustered_p != null && ` Treating each company as one block gives p = ${pValue(reg.clustered_p)}.`}
    </>
  );
}

// key numbers table

const WINDOW_COLUMNS: [string, string][] = [
  ["CAR[-10,-1]", "Days -10 to -1"],
  ["AR[0]", "Day 0"],
  ["CAR[0,+1]", "Days 0 to +1"],
  ["CAR[+1,+10]", "Days +1 to +10"],
];

function KeyNumbers({ data }: { data: Research }) {
  return (
    <section className="card">
      <div className="card-header flex-col items-start gap-0.5">
        <h2 className="font-semibold text-text">Key numbers</h2>
        <p className="text-xs text-muted">
          Average abnormal return vs {data.settings.market} (market model); t-statistic and p-value under each
        </p>
      </div>
      <div className="card-body overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead>
            <tr className="text-left stat-label">
              <th className="py-2 pr-3 font-medium">Group</th>
              <th className="py-2 px-3 font-medium text-right">n</th>
              {WINDOW_COLUMNS.map(([, label]) => (
                <th key={label} className="py-2 px-3 font-medium text-right">{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.windows.map((g) => (
              <tr key={g.key} className="border-t border-border align-top">
                <td className="py-2 pr-3">
                  <div className="text-text">{g.label}</div>
                  {(g.key === "large_cap" || g.key === "small_cap") && (
                    <div className="text-xs text-muted">{g.tickers.join(", ")}</div>
                  )}
                </td>
                <td className="py-2 px-3 text-right font-mono text-muted">{g.n}</td>
                {WINDOW_COLUMNS.map(([name]) => {
                  const s = g.stats[name];
                  return (
                    <td key={name} className="py-2 px-3 text-right">
                      <div className={`font-mono ${isSig(s.p) ? "text-accent font-semibold" : "text-text"}`}>
                        {pct(s.mean)}
                      </div>
                      <div className="text-xs text-muted font-mono">
                        t {s.t == null ? "-" : s.t.toFixed(2)} · p {pValue(s.p, 3)}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-muted mt-3">Highlighted: p below 0.05.</p>
      </div>
    </section>
  );
}

// method + limitations

function Method({ data }: { data: Research }) {
  const { settings: s, coverage } = data;
  const missing = Object.keys(coverage.not_in_drugsfda);
  return (
    <section className="card">
      <div className="card-header"><h2 className="font-semibold text-text">Method</h2></div>
      <div className="card-body">
        <ul className="list-disc pl-5 space-y-1.5 text-sm text-text/90 leading-relaxed">
          <li>
            Market model: each stock&apos;s daily returns are regressed on {s.market} (SPDR S&amp;P Biotech ETF)
            over trading days {s.estimation_window[0]} to {s.estimation_window[1]} before the event. The abnormal
            return is the actual return minus what that alpha and beta predict. Events with under 120 days of
            estimation data are skipped.
          </li>
          <li>
            Event window: days {s.event_window[0]} to +{s.event_window[1]}. Day 0 is the first trading day on or
            after the approval date. Cumulative returns (CAR) start at day {s.event_window[0]}.
          </li>
          <li>
            Several approvals of one company on the same day count as one event. An event is dropped when the
            same company has another one within ±{s.cluster_days} trading days.
          </li>
          <li>
            Approvals: original approvals and new-indication supplements from OpenFDA (drugsfda), last {s.years}{" "}
            years. Prices: daily adjusted closes from yfinance. Statistics are across events (t-tests on the
            average).
          </li>
          <li>
            Coverage gap: vaccines and gene therapies are CBER products and are not in OpenFDA&apos;s drugsfda
            data, so {missing.join(", ")} have no events. {coverage.no_approved_products.join(" and ")} have no
            approved products yet. The results describe the other companies&apos; drugs and biologics.
          </li>
        </ul>
      </div>
    </section>
  );
}

function Limitations({ data }: { data: Research }) {
  const others = data.windows.find((w) => w.key === "small_cap")!;
  return (
    <section className="card">
      <div className="card-header"><h2 className="font-semibold text-text">Limitations</h2></div>
      <div className="card-body">
        <ul className="list-disc pl-5 space-y-1.5 text-sm text-text/90 leading-relaxed">
          <li>
            Small sample: {data.events} events from {data.companies} companies. Confidence bands are wide, and
            most results are not statistically significant.
          </li>
          <li>
            The clearest reaction comes from {others.tickers.join(", ")} ({others.n} events); large companies
            barely move on a single approval.
          </li>
          <li>
            Events from the same company are not independent, so p-values are optimistic.
          </li>
          <li>
            Many windows, groups and strategies were tested on the same sample, so some &quot;significant&quot;
            results can be luck.
          </li>
          <li>
            OpenFDA gives the FDA action date, not the time of the announcement, and approvals that were widely
            expected are mostly priced in before day 0.
          </li>
          <li>
            Strategies A and B assume the approval date was known {Math.abs(data.settings.event_window[0]) + 1}{" "}
            trading days ahead, and ignore slippage, taxes and position sizing.
          </li>
        </ul>
      </div>
    </section>
  );
}

// page

function Skeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card p-4 space-y-3">
            <div className="h-3 bg-border rounded w-1/2" />
            <div className="h-7 bg-border rounded w-2/3" />
            <div className="h-3 bg-border rounded w-full" />
          </div>
        ))}
      </div>
      {Array.from({ length: 2 }).map((_, i) => (
        <div key={i} className="card p-5">
          <div className="h-4 bg-border rounded w-1/3 mb-4" />
          <div className="h-72 bg-border rounded" />
        </div>
      ))}
    </div>
  );
}

export default function ResearchPage() {
  const [data, setData] = useState<Research | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false; // ignore a late response after leaving the page
    loadResearch()
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message || "Could not load research data"));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Research</h1>
        <p className="text-sm text-muted mt-0.5">How biotech stocks react to FDA approvals</p>
        {data && (
          <p className="text-xs text-muted mt-1 font-mono">
            {data.events} events · {data.companies} companies · {data.first_event.slice(0, 7)} to{" "}
            {data.last_event.slice(0, 7)} · updated {data.generated}
          </p>
        )}
      </div>

      {error ? (
        <div className="card p-8 text-center">
          <AlertTriangle className="h-10 w-10 text-warning mx-auto mb-3" />
          <p className="text-danger font-medium">{error}</p>
        </div>
      ) : !data ? (
        <Skeleton />
      ) : (
        <>
          <Tiles data={data} />

          <Section
            title="Daily reaction"
            subtitle={`Average abnormal return per day around the approval, with 95% error bars (n = ${data.daily_ar.n})`}
            meaning={dailyMeaning(data)}
          >
            <DailyChart data={data} />
          </Section>

          <Section
            title="Cumulative reaction"
            subtitle="Running total of the abnormal return from day -10"
            meaning={carMeaning(data)}
          >
            <CarChart data={data} />
          </Section>

          <Section
            title="Original approvals vs new indications"
            subtitle="Same cumulative view, split by type of approval (market model)"
            meaning={typeMeaning(data)}
          >
            <TypeChart data={data} />
          </Section>

          <KeyNumbers data={data} />

          <Section
            title="Trading around the news"
            subtitle={`Average abnormal return per trade, with 95% error bars (n = ${data.strategies[0].n} approvals)`}
            meaning={strategyMeaning(data)}
          >
            <StrategyChart data={data} />
            <StrategyTable data={data} />
          </Section>

          <Section
            title="Run-up vs reaction"
            subtitle="One dot per approval: the move before it against the move after it (days +2 to +10)"
            meaning={scatterMeaning(data)}
          >
            <ScatterPlot data={data} />
          </Section>

          <Method data={data} />
          <Limitations data={data} />
        </>
      )}

      <p className="text-xs text-muted border-t border-border pt-4">Historical analysis, not investment advice.</p>
    </div>
  );
}
