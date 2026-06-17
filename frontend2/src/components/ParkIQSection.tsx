import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface DecayPoint {
  day: number;
  date: string;
  violations: number;
}

interface HeatmapCell {
  day: string;
  hour: string;
  intensity: number;
}

const getHeatmapColor = (intensity: number) => {
  if (intensity < 20) return 'bg-success/10 text-success';
  if (intensity < 50) return 'bg-warning/20 text-warning';
  if (intensity < 80) return 'bg-orange-500/30 text-orange-400';
  return 'bg-destructive/40 text-destructive font-bold';
};

export function ParkIQSection() {
  const [decayCurve, setDecayCurve] = useState<DecayPoint[]>([]);
  const [heatmap, setHeatmap] = useState<Record<string, HeatmapCell[]>>({});
  const [activeZone, setActiveZone] = useState('Silk Board Junction');

  useEffect(() => {
    fetch('http://localhost:8000/api/parkiq/deterrence-decay')
      .then(r => r.json())
      .then(d => setDecayCurve(d.decay_curve || []))
      .catch(() => {});

    fetch('http://localhost:8000/api/parkiq/heatmap')
      .then(r => r.json())
      .then(d => setHeatmap(d.heatmap || {}))
      .catch(() => {});
  }, []);

  const currentHeatmap = heatmap[activeZone] || [];
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Deterrence Decay Curve */}
        <div className="dashboard-card">
          <h3 className="text-sm font-semibold text-foreground mb-1">Deterrence Decay Curve</h3>
          <p className="text-xs text-muted-foreground mb-4">Post-patrol violation recovery over 30 days</p>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={decayCurve}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 17%)" />
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#9ca3af' }} />
                <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'hsl(222 47% 8%)', border: '1px solid hsl(217 33% 17%)' }}
                  labelStyle={{ color: '#9ca3af', fontSize: '12px' }}
                />
                <Line type="monotone" dataKey="violations" stroke="#f97316" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Heatmap Matrix */}
        <div className="dashboard-card flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Hotspot Heatmap</h3>
              <p className="text-xs text-muted-foreground">Violation intensity (24h x 7d)</p>
            </div>
            <select
              className="bg-secondary text-xs text-foreground border border-border rounded px-2 py-1"
              value={activeZone}
              onChange={(e) => setActiveZone(e.target.value)}
            >
              <option value="Silk Board Junction">Silk Board Junction</option>
              <option value="KR Market">KR Market</option>
              <option value="MG Road">MG Road</option>
            </select>
          </div>
          
          <div className="flex-1 overflow-x-auto">
            {currentHeatmap.length > 0 ? (
              <div className="min-w-[500px] text-[10px]">
                <div className="grid grid-cols-[40px_repeat(24,1fr)] gap-0.5 mb-0.5">
                  <div />
                  {Array.from({ length: 24 }).map((_, i) => (
                    <div key={i} className="text-center text-muted-foreground">{i}h</div>
                  ))}
                </div>
                {days.map(day => (
                  <div key={day} className="grid grid-cols-[40px_repeat(24,1fr)] gap-0.5 mb-0.5">
                    <div className="text-muted-foreground flex items-center font-medium">{day}</div>
                    {currentHeatmap.filter(c => c.day === day).map((cell, i) => (
                      <div
                        key={i}
                        className={`aspect-square rounded-[2px] ${getHeatmapColor(cell.intensity)}`}
                        title={`${day} ${cell.hour}: ${cell.intensity} violations`}
                      />
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
                Loading heatmap data...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
