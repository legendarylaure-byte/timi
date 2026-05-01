'use client';

import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

const data = [
  { day: 'Mon', growth: 12 },
  { day: 'Tue', growth: 18 },
  { day: 'Wed', growth: 24 },
  { day: 'Thu', growth: 15 },
  { day: 'Fri', growth: 32 },
  { day: 'Sat', growth: 41 },
  { day: 'Sun', growth: 28 },
];

export function GrowthChart() {
  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis dataKey="day" stroke="#6B7280" fontSize={12} />
          <YAxis stroke="#6B7280" fontSize={12} />
          <Tooltip />
          <Line type="monotone" dataKey="growth" stroke="#FF6B6B" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
