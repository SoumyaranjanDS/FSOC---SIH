import { useEffect, useRef, useState } from "react";
import BenchmarkModal from "./BenchmarkModal";
import BenchmarkPanel from "./BenchmarkPanel";

function useVideoBenchmark({
  socket,
  telemetry,
  engineStatus,
  onClearTelemetry,
}) {
  const [benchmarkFile, setBenchmarkFile] = useState(null);
  const [benchmarkSummary, setBenchmarkSummary] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const videoRef = useRef(null);

  useEffect(() => {
    const handleBenchmarkComplete = (data) => {
      if (videoRef.current) videoRef.current.pause();
      setBenchmarkSummary(data.summary);
    };

    socket.on("benchmark_complete", handleBenchmarkComplete);
    return () => socket.off("benchmark_complete", handleBenchmarkComplete);
  }, [socket]);

  const handleUpload = async (file) => {
    if (!file) return;
    setIsUploading(true);
    const formData = new FormData();
    formData.append("video", file);
    try {
      const response = await fetch("http://localhost:3000/upload_video", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`Upload failed with status ${response.status}`);
      }
      setBenchmarkFile(await response.json());
    } catch (error) {
      console.error("Video upload failed", error);
      setBenchmarkFile(null);
    } finally {
      setIsUploading(false);
    }
  };

  const start = () => {
    if (!benchmarkFile) return;
    setBenchmarkSummary(null);
    onClearTelemetry();
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.play().catch(() => {});
    }
    socket.emit("start_benchmark", { video_path: benchmarkFile.path });
  };

  const stop = () => socket.emit("stop_benchmark");
  const reset = () => {
    stop();
    setBenchmarkSummary(null);
    onClearTelemetry();
    if (videoRef.current) videoRef.current.currentTime = 0;
  };

  const panel = (
    <BenchmarkPanel
      benchmarkFile={benchmarkFile}
      isUploading={isUploading}
      engineStatus={engineStatus}
      telemetry={telemetry}
      onUpload={handleUpload}
      onStart={start}
      onStop={stop}
      onReset={reset}
    />
  );

  const stage = benchmarkFile ? (
    <div className="benchmark-video-stage">
      <video
        ref={videoRef}
        src={benchmarkFile.url}
        controls
        muted
        playsInline
      />
    </div>
  ) : null;

  const modal = benchmarkSummary ? (
    <BenchmarkModal
      telemetry={{
        performance: {
          acquisition_time: benchmarkSummary.acquisition_time_sec,
          avg_error: benchmarkSummary.avg_centroid_error,
          max_error: benchmarkSummary.max_centroid_error,
          lock_retention_rate: benchmarkSummary.lock_retention_rate,
          reacquisition_time: benchmarkSummary.avg_reacquisition_sec,
          fps: benchmarkSummary.processing_fps,
        },
      }}
      onClose={() => setBenchmarkSummary(null)}
    />
  ) : null;

  return { panel, stage, modal };
}

export default useVideoBenchmark;
