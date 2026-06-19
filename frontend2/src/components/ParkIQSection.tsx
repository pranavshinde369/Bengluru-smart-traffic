import { useState, useEffect } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  BarChart, Bar, ScatterChart, Scatter, ZAxis, ReferenceLine
} from 'recharts';

export function ParkIQSection() {
  const [clusters, setClusters] = useState<any>(null);
  const [congestion, setCongestion] = useState<any>(null);
  const [deterrence, setDeterrence] = useState<any>(null);
  const [heatmap, setHeatmap] = useState<any>(null);
  const [repeatOffenders, setRepeatOffenders] = useState<any>(null);
  const [hoveredCell, setHoveredCell] = useState<{ day: string; hour: number; intensity: number } | null>(null);

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/parkiq/clusters`).then(r => r.json()).then(setClusters).catch(() => {});
    fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/parkiq/congestion-scores`).then(r => r.json()).then(setCongestion).catch(() => {});
    fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/parkiq/deterrence-decay`).then(r => r.json()).then(setDeterrence).catch(() => {});
    fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/parkiq/heatmap`).then(r => r.json()).then(setHeatmap).catch(() => {});
    fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/parkiq/repeat-offenders`).then(r => r.json()).then(setRepeatOffenders).catch(() => {});
  }, []);

  const getHeatmapColor = (intensity: number, max: number) => {
    if (intensity === 0) return 'bg-secondary/20';
    const ratio = intensity / (max || 1);
    if (ratio < 0.1) return 'bg-emerald-500/20';
    if (ratio < 0.25) return 'bg-emerald-500/40';
    if (ratio < 0.4) return 'bg-yellow-500/50';
    if (ratio < 0.6) return 'bg-orange-500/60';
    if (ratio < 0.8) return 'bg-orange-600/80';
    return 'bg-red-600';
  };

  const heatmapMax = heatmap ? Math.max(...heatmap.matrix.flat()) : 1;

  let peak = { day: '', hour: 0, intensity: -1 };
  let safest = { day: '', hour: 0, intensity: Infinity };
  const dayTotals: Record<string, number> = {};

  if (heatmap) {
    heatmap.days.forEach((day: string, rIdx: number) => {
      let dayTotal = 0;
      heatmap.matrix[rIdx].forEach((intensity: number, cIdx: number) => {
        dayTotal += intensity;
        if (intensity > peak.intensity) {
          peak = { day, hour: heatmap.hours[cIdx], intensity };
        }
        if (intensity < safest.intensity) {
          safest = { day, hour: heatmap.hours[cIdx], intensity };
        }
      });
      dayTotals[day] = dayTotal;
    });
  }
  
  const busiestDay = Object.keys(dayTotals).length > 0 
    ? Object.keys(dayTotals).reduce((a, b) => dayTotals[a] > dayTotals[b] ? a : b) 
    : '';

  return (
    <div className="space-y-4">
      {/* Hotspot Callout */}
      <div className="dashboard-card bg-destructive/10 border-destructive/20 shadow-sm">
        <h3 className="text-lg font-bold text-destructive">Top Hotspot: Safina Plaza Junction</h3>
        <p className="text-sm text-foreground mt-1">
          Safina Plaza is the #1 real hotspot with <strong>15,449</strong> violations, beating KR Market's 11,538, based on five months of real enforcement data.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Congestion Ranking */}
        <div className="dashboard-card">
          <h3 className="text-sm font-semibold text-foreground mb-1">Congestion Impact Ranking</h3>
          <p className="text-xs text-muted-foreground mb-4">Relative index (density + severity)</p>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={congestion?.junctions?.sort((a: any, b: any) => b.congestion_score - a.congestion_score) || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 17%)" />
                <XAxis dataKey="junction" tick={{ fontSize: 10, fill: '#9ca3af' }} interval={0} angle={-30} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} />
                <RechartsTooltip 
                  contentStyle={{ backgroundColor: 'hsl(222 47% 8%)', border: '1px solid hsl(217 33% 17%)', borderRadius: '8px' }}
                  labelStyle={{ color: '#9ca3af', fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}
                  itemStyle={{ fontSize: '12px' }}
                  formatter={(val: number) => [val.toFixed(2), "Relative Score"]}
                />
                <Bar dataKey="congestion_score" fill="#f97316" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Deterrence Decay */}
        <div className="dashboard-card">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="text-sm font-semibold text-foreground mb-1">Deterrence Decay</h3>
              <p className="text-xs text-muted-foreground">Post-enforcement recovery</p>
            </div>
            {deterrence?.days_to_80pct_recovery && (
              <div className="text-right">
                <div className="text-2xl font-bold text-orange-500">{deterrence.days_to_80pct_recovery} Days</div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">to 80% Recovery</div>
              </div>
            )}
          </div>
          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={deterrence?.series || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 17%)" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} minTickGap={30} />
                <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} />
                <RechartsTooltip 
                  contentStyle={{ backgroundColor: 'hsl(222 47% 8%)', border: '1px solid hsl(217 33% 17%)', borderRadius: '8px' }}
                  labelStyle={{ color: '#9ca3af', fontSize: '12px', fontWeight: 'bold' }}
                />
                <Line type="monotone" dataKey="violations" stroke="#f97316" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#f97316' }} />
                {deterrence?.drop_date && (
                  <ReferenceLine x={deterrence.drop_date} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'top', value: 'Enforcement Drop', fill: '#ef4444', fontSize: 10, fontWeight: 'bold' }} />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Repeat Offenders */}
        <div className="dashboard-card flex flex-col justify-center">
          <h3 className="text-sm font-semibold text-foreground mb-1">Repeat Offenders</h3>
          <p className="text-xs text-muted-foreground mb-4">Five months of real enforcement data</p>
          {repeatOffenders ? (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-5 bg-secondary/30 rounded-xl border border-border shadow-sm flex flex-col items-center justify-center text-center">
                  <div className="text-4xl font-black text-primary">{repeatOffenders.repeat_vehicle_share_pct.toFixed(1)}%</div>
                  <div className="text-xs text-muted-foreground mt-2 font-medium">of vehicles are<br/>repeat offenders</div>
                </div>
                <div className="p-5 bg-destructive/10 rounded-xl border border-destructive/20 shadow-sm flex flex-col items-center justify-center text-center">
                  <div className="text-4xl font-black text-destructive">{repeatOffenders.violations_from_repeat_vehicles_share_pct.toFixed(1)}%</div>
                  <div className="text-xs text-muted-foreground mt-2 font-medium">of all violations<br/>are caused by them</div>
                </div>
              </div>
              <div className="mt-2 text-center text-sm text-foreground bg-secondary/20 p-3 rounded-lg border border-border">
                The worst single vehicle was caught <strong className="text-orange-500">{repeatOffenders.most_frequent_vehicle_violation_count} times</strong>.
              </div>
            </div>
          ) : (
             <div className="text-xs text-muted-foreground flex h-full items-center justify-center">Loading...</div>
          )}
        </div>

        {/* Cluster Map */}
        <div className="dashboard-card">
          <h3 className="text-sm font-semibold text-foreground mb-1">Violation Clusters</h3>
          <p className="text-xs text-muted-foreground mb-4">Spatial distribution across Bengaluru</p>
          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 17%)" />
                <XAxis type="number" dataKey="lng" name="Longitude" domain={['dataMin - 0.01', 'dataMax + 0.01']} tick={{ fontSize: 10, fill: '#9ca3af' }} tickFormatter={(val) => val.toFixed(2)} />
                <YAxis type="number" dataKey="lat" name="Latitude" domain={['dataMin - 0.01', 'dataMax + 0.01']} tick={{ fontSize: 10, fill: '#9ca3af' }} tickFormatter={(val) => val.toFixed(2)} />
                <ZAxis type="number" dataKey="estimated_full_dataset_count" range={[40, 400]} name="Violations" />
                <RechartsTooltip cursor={{ strokeDasharray: '3 3' }} 
                  contentStyle={{ backgroundColor: 'hsl(222 47% 8%)', border: '1px solid hsl(217 33% 17%)', borderRadius: '8px' }}
                  itemStyle={{ color: '#9ca3af', fontSize: '12px' }}
                />
                <Scatter data={clusters?.clusters || []} fill="#22d3ee" fillOpacity={0.7} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Heatmap */}
        <div className="dashboard-card lg:col-span-2">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
            <div>
              <h3 className="text-sm font-semibold text-foreground mb-1">Violation Heatmap</h3>
              <p className="text-xs text-muted-foreground">7x24 grid of violation intensity over five months</p>
            </div>
            
            {heatmap && (
              <div className="flex gap-4 bg-secondary/10 p-3 rounded-lg border border-border/50">
                <div className="text-right">
                  <div className="text-xs text-muted-foreground">Peak Violation</div>
                  <div className="text-sm font-bold text-destructive">{peak.day.substring(0, 3)} at {peak.hour}:00</div>
                  <div className="text-[10px] text-muted-foreground">{peak.intensity.toLocaleString()} violations</div>
                </div>
                <div className="text-right border-l border-border pl-4">
                  <div className="text-xs text-muted-foreground">Safest Time</div>
                  <div className="text-sm font-bold text-success">{safest.day.substring(0, 3)} at {safest.hour}:00</div>
                  <div className="text-[10px] text-muted-foreground">{safest.intensity.toLocaleString()} violations</div>
                </div>
                <div className="text-right border-l border-border pl-4">
                  <div className="text-xs text-muted-foreground">Busiest Day</div>
                  <div className="text-sm font-bold text-orange-500">{busiestDay}</div>
                  <div className="text-[10px] text-muted-foreground">{dayTotals[busiestDay]?.toLocaleString()} violations</div>
                </div>
              </div>
            )}
          </div>

          <div className="overflow-x-auto pb-4">
            {heatmap ? (
              <div className="min-w-[700px] text-[10px]">
                {/* Header */}
                <div className="grid grid-cols-[60px_repeat(24,1fr)] gap-1 mb-2">
                  <div />
                  {heatmap.hours.map((h: number) => (
                    <div key={h} className={`text-center font-semibold transition-colors ${hoveredCell?.hour === h ? 'text-foreground' : 'text-muted-foreground'}`}>{h}h</div>
                  ))}
                </div>
                {/* Grid */}
                <div className="relative">
                  {heatmap.days.map((day: string, rIdx: number) => (
                    <div key={day} className="grid grid-cols-[60px_repeat(24,1fr)] gap-1 mb-1">
                      <div className={`flex items-center justify-end pr-2 font-medium transition-colors ${hoveredCell?.day === day ? 'text-foreground' : 'text-muted-foreground'}`}>
                        {day.substring(0, 3)}
                      </div>
                      {heatmap.matrix[rIdx].map((intensity: number, cIdx: number) => {
                        const h = heatmap.hours[cIdx];
                        const isHovered = hoveredCell?.day === day && hoveredCell?.hour === h;
                        const isRowHovered = hoveredCell?.day === day;
                        const isColHovered = hoveredCell?.hour === h;
                        const opacity = (isHovered || (!hoveredCell)) ? 'opacity-100' : (isRowHovered || isColHovered) ? 'opacity-70' : 'opacity-30';
                        
                        return (
                          <div
                            key={cIdx}
                            onMouseEnter={() => setHoveredCell({ day, hour: h, intensity })}
                            onMouseLeave={() => setHoveredCell(null)}
                            className={`aspect-square rounded-[3px] ${getHeatmapColor(intensity, heatmapMax)} ${opacity} transition-all duration-200 cursor-pointer ${isHovered ? 'scale-125 ring-2 ring-foreground z-20 shadow-lg' : 'z-10'}`}
                          />
                        );
                      })}
                    </div>
                  ))}
                </div>
                
                {/* Legend & Tooltip Area */}
                <div className="mt-6 flex justify-between items-center bg-secondary/10 p-3 rounded-lg border border-border/50">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground font-medium mr-2">Intensity:</span>
                    <div className="flex items-center gap-1"><div className="w-3 h-3 rounded-sm bg-secondary/20"></div><span className="text-[10px] text-muted-foreground">0</span></div>
                    <div className="flex items-center gap-1"><div className="w-3 h-3 rounded-sm bg-emerald-500/20"></div><span className="text-[10px] text-muted-foreground">Low</span></div>
                    <div className="flex items-center gap-1"><div className="w-3 h-3 rounded-sm bg-yellow-500/50"></div><span className="text-[10px] text-muted-foreground">Medium</span></div>
                    <div className="flex items-center gap-1"><div className="w-3 h-3 rounded-sm bg-orange-500/80"></div><span className="text-[10px] text-muted-foreground">High</span></div>
                    <div className="flex items-center gap-1"><div className="w-3 h-3 rounded-sm bg-red-600"></div><span className="text-[10px] text-muted-foreground">Max</span></div>
                  </div>
                  
                  <div className="h-8 flex items-center justify-end min-w-[200px]">
                    {hoveredCell ? (
                      <div className="text-right">
                        <span className="text-foreground font-bold">{hoveredCell.day} at {hoveredCell.hour}:00</span>
                        <span className="mx-2 text-muted-foreground">|</span>
                        <span className="text-primary font-bold">{hoveredCell.intensity.toLocaleString()} violations</span>
                      </div>
                    ) : (
                      <span className="text-muted-foreground italic">Hover over a cell for details</span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-48 text-muted-foreground">Loading heatmap data...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
