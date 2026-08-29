import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import type { PortfolioSnapshot } from "../lib/types";

export function EquityChart({ data, startingBalance }: { data: PortfolioSnapshot[]; startingBalance: number }) {
  const points = data.map((s) => ({ t: s.timestamp, equity: s.equitySol }));
  const up = points.length === 0 || points[points.length - 1].equity >= startingBalance;

  return (
    <div className="h-16 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={up ? "gradUp" : "gradDown"} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={up ? "#00c853" : "#ff3b3b"} stopOpacity={0.35} />
              <stop offset="100%" stopColor={up ? "#00c853" : "#ff3b3b"} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis domain={["dataMin", "dataMax"]} hide />
          <Tooltip
            contentStyle={{ background: "#161b26", border: "1px solid #232a38", borderRadius: 8, fontSize: 12 }}
            labelFormatter={() => ""}
            formatter={(v: number) => [`${v.toFixed(4)} SOL`, "équité"]}
          />
          <Area
            type="monotone"
            dataKey="equity"
            stroke={up ? "#00c853" : "#ff3b3b"}
            fill={`url(#${up ? "gradUp" : "gradDown"})`}
            strokeWidth={1.5}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
