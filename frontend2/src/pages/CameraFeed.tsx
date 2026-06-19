import { useState, useEffect, useCallback } from 'react';
import { DashboardSidebar } from '@/components/DashboardSidebar';
import { DashboardHeader } from '@/components/DashboardHeader';
import { Wifi, Loader2, Camera, Info, Edit3 } from 'lucide-react';

const cameras = [
  { id: '04', label: 'Camera 04 — Silk Board Junction' },
  { id: '01', label: 'Camera 01 — KR Market' },
  { id: '02', label: 'Camera 02 — MG Road' },
  { id: '03', label: 'Camera 03 — Hebbal' },
];

const CameraFeed = () => {
  const [selectedCamera, setSelectedCamera] = useState('04');
  const [error, setError] = useState(false);
  const [time, setTime] = useState(new Date());
  const [fps, setFps] = useState(26);
  const [latency, setLatency] = useState(15);
  const [vehicleCount, setVehicleCount] = useState(0);

  // Geofencing state
  const [isDrawing, setIsDrawing] = useState(false);
  const [polygonPoints, setPolygonPoints] = useState<{x: number, y: number}[]>([]);
  const [isSaving, setIsSaving] = useState(false);

  const handleSvgClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawing) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round((e.clientX - rect.left) / rect.width * 640);
    const y = Math.round((e.clientY - rect.top) / rect.height * 480);
    setPolygonPoints(prev => [...prev, { x, y }]);
  };

  const saveGeofence = async () => {
    if (polygonPoints.length < 3) {
      alert("Please draw at least 3 points to form a polygon.");
      return;
    }
    setIsSaving(true);
    try {
      await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ geofence_polygon: polygonPoints })
      });
      setIsDrawing(false);
      setPolygonPoints([]);
    } catch (err) {
      console.error("Failed to save geofence", err);
    } finally {
      setIsSaving(false);
    }
  };

  useEffect(() => {
    const t = setInterval(() => {
      setTime(new Date());
      setFps(24 + Math.floor(Math.random() * 5));
      setLatency(12 + Math.floor(Math.random() * 7));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  const fetchVehicles = useCallback(async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/traffic-data`);
      if (!res.ok) return;
      const json = await res.json();
      setVehicleCount(json.vehicle_count ?? 0);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchVehicles();
    const t = setInterval(fetchVehicles, 1000);
    return () => clearInterval(t);
  }, [fetchVehicles]);

  useEffect(() => {
    setError(false);
  }, [selectedCamera]);

  const statItems = [
    { label: 'FPS', value: `${fps}` },
    { label: 'Resolution', value: '640×480' },
    { label: 'Detections', value: String(vehicleCount) },
    { label: 'Latency', value: `${latency}ms` },
  ];

  return (
    <div className="flex min-h-screen bg-background">
      <DashboardSidebar />
      <main className="flex-1 ml-[220px] transition-all duration-300 min-h-screen flex flex-col">
        <DashboardHeader />
        <div className="flex-1 p-6 flex flex-col gap-4 overflow-y-auto">
          {/* Camera selector */}
          <div className="flex items-center gap-3 flex-wrap">
            {cameras.map((cam) => (
              <button
                key={cam.id}
                onClick={() => setSelectedCamera(cam.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
                  selectedCamera === cam.id
                    ? 'bg-primary/15 text-primary border-primary/40'
                    : 'bg-card text-muted-foreground border-border hover:text-foreground hover:border-muted-foreground/30'
                }`}
              >
                <Camera className="w-4 h-4" />
                {cam.label}
              </button>
            ))}
          </div>

          {/* Stats bar */}
          <div className="flex items-center gap-6 px-4 py-2.5 bg-card rounded-lg border border-border">
            {statItems.map((s) => (
              <div key={s.label} className="flex items-center gap-2">
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{s.label}</span>
                <span className="text-sm font-mono font-semibold text-foreground">{s.value}</span>
              </div>
            ))}
          </div>

          {/* Video feed */}
          <div className="dashboard-card relative overflow-hidden">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-foreground">
                Live AI CCTV Feed — {cameras.find(c => c.id === selectedCamera)?.label}
              </h3>
              <div className="flex items-center gap-2">
                {!isDrawing ? (
                  <button
                    onClick={() => setIsDrawing(true)}
                    className="text-xs bg-primary/20 text-primary px-2 py-1 rounded flex items-center gap-1 hover:bg-primary/30 transition-colors"
                  >
                    <Edit3 className="w-3 h-3" /> Draw Geofence
                  </button>
                ) : (
                  <>
                    <button
                      onClick={saveGeofence}
                      disabled={isSaving}
                      className="text-xs bg-success/20 text-success px-2 py-1 rounded flex items-center gap-1 hover:bg-success/30 transition-colors"
                    >
                      {isSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wifi className="w-3 h-3 hidden" />}
                      Save Zone
                    </button>
                    <button
                      onClick={() => { setIsDrawing(false); setPolygonPoints([]); }}
                      className="text-xs bg-alert/20 text-alert px-2 py-1 rounded flex items-center gap-1 hover:bg-alert/30 transition-colors"
                    >
                      <Wifi className="w-3 h-3 hidden" /> Cancel
                    </button>
                  </>
                )}
                <span className="text-xs bg-success/20 text-success px-2 py-0.5 rounded-full font-mono">
                  YOLOv8n Active
                </span>
              </div>
            </div>

            <div className="relative w-full rounded-lg overflow-hidden bg-secondary" style={{ aspectRatio: '16/9', maxHeight: 480 }}>
              {error ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-muted-foreground">
                  <Wifi className="w-10 h-10" />
                  <span className="text-sm">Connecting to AI Engine...</span>
                  <Loader2 className="w-5 h-5 animate-spin" />
                </div>
              ) : (
                <img
                  src={`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/video-feed`}
                  alt="Live CCTV Feed"
                  className="w-full h-full object-cover"
                  onError={() => setError(true)}
                />
              )}

              {isDrawing && (
                <svg 
                  className="absolute inset-0 w-full h-full cursor-crosshair z-10" 
                  viewBox="0 0 640 480"
                  preserveAspectRatio="none"
                  onClick={handleSvgClick}
                >
                  <rect width="640" height="480" fill="rgba(0,0,0,0.1)" />
                  {polygonPoints.length > 0 && (
                    <polygon
                      points={polygonPoints.map(p => `${p.x},${p.y}`).join(' ')}
                      fill="rgba(0, 100, 255, 0.2)"
                      stroke="rgba(0, 200, 255, 0.8)"
                      strokeWidth="3"
                      strokeDasharray="5,5"
                    />
                  )}
                  {polygonPoints.map((p, i) => (
                    <circle key={i} cx={p.x} cy={p.y} r="5" fill="white" stroke="rgba(0, 200, 255, 0.8)" strokeWidth="2" />
                  ))}
                </svg>
              )}

              {/* Scanline overlay */}
              <div className="absolute inset-0 pointer-events-none scanline-overlay" />

              <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-background/70 backdrop-blur-sm px-2 py-1 rounded text-xs z-20">
                <span className="w-2 h-2 rounded-full bg-alert pulse-live" />
                <span className="text-alert font-bold font-mono">LIVE</span>
              </div>

              <div className="absolute bottom-3 right-3 bg-background/70 backdrop-blur-sm px-2 py-1 rounded text-xs text-muted-foreground font-mono z-20">
                {time.toLocaleTimeString()}
              </div>

              {isDrawing && (
                <div className="absolute bottom-3 left-3 bg-background/80 backdrop-blur-sm px-3 py-1.5 rounded text-xs text-foreground font-medium animate-pulse border border-primary/30 z-20 pointer-events-none">
                  Click on the video to draw a No-Parking Zone polygon
                </div>
              )}
            </div>
          </div>

          {/* Info card */}
          <div className="flex items-start gap-3 px-4 py-3 bg-card rounded-lg border border-border text-xs text-muted-foreground">
            <Info className="w-4 h-4 flex-shrink-0 mt-0.5 text-primary" />
            <span>
              All cameras share the same AI engine backend. In production, each camera runs an independent YOLO inference thread.
            </span>
          </div>
        </div>
      </main>
    </div>
  );
};

export default CameraFeed;
