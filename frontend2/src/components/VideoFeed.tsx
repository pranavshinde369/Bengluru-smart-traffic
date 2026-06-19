import { useState, useEffect } from 'react';
import { Wifi, Loader2, Edit3, Save, X } from 'lucide-react';

export function VideoFeed() {
  const [error, setError] = useState(false);
  const [time, setTime] = useState(new Date());
  
  // Geofencing state
  const [isDrawing, setIsDrawing] = useState(false);
  const [polygonPoints, setPolygonPoints] = useState<{x: number, y: number}[]>([]);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Auto-retry connection every 3 seconds if error occurs
  useEffect(() => {
    if (error) {
      const retryTimer = setTimeout(() => setError(false), 3000);
      return () => clearTimeout(retryTimer);
    }
  }, [error]);

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

  return (
    <div className="dashboard-card relative overflow-hidden">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-foreground">Live AI CCTV Feed — Camera 04</h3>
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
                {isSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                Save Zone
              </button>
              <button
                onClick={() => { setIsDrawing(false); setPolygonPoints([]); }}
                className="text-xs bg-alert/20 text-alert px-2 py-1 rounded flex items-center gap-1 hover:bg-alert/30 transition-colors"
              >
                <X className="w-3 h-3" /> Cancel
              </button>
            </>
          )}
          <span className="text-xs bg-success/20 text-success px-2 py-0.5 rounded-full font-mono">
            YOLOv8n Active
          </span>
        </div>
      </div>

      <div className="relative h-[360px] aspect-video rounded-lg overflow-hidden bg-secondary">
        {error ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <Wifi className="w-8 h-8" />
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
            className="absolute inset-0 w-full h-full cursor-crosshair" 
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

        {/* LIVE badge */}
        <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-background/70 backdrop-blur-sm px-2 py-1 rounded text-xs">
          <span className="w-2 h-2 rounded-full bg-alert pulse-live" />
          <span className="text-alert font-bold font-mono">LIVE</span>
        </div>

        {/* Timestamp */}
        <div className="absolute bottom-3 right-3 bg-background/70 backdrop-blur-sm px-2 py-1 rounded text-xs text-muted-foreground font-mono pointer-events-none">
          {time.toLocaleTimeString()}
        </div>
        
        {isDrawing && (
          <div className="absolute bottom-3 left-3 bg-background/80 backdrop-blur-sm px-3 py-1.5 rounded text-xs text-foreground font-medium animate-pulse border border-primary/30 pointer-events-none">
            Click on the video to draw a No-Parking Zone polygon
          </div>
        )}
      </div>
    </div>
  );
}
