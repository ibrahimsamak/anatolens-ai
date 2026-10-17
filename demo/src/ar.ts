export type ARMode = "webxr" | "native" | "pseudo" | "none";

export async function bestARMode(mv: { canActivateAR?: boolean } | null): Promise<ARMode> {
  const xr = (navigator as Navigator & { xr?: { isSessionSupported?: (m: string) => Promise<boolean> } }).xr;
  if (xr && (await xr.isSessionSupported?.("immersive-ar").catch(() => false))) return "webxr";
  if (mv?.canActivateAR) return "native";
  if (typeof navigator.mediaDevices?.getUserMedia === "function") return "pseudo";
  return "none";
}

export async function startPseudoAR(video: HTMLVideoElement): Promise<() => void> {
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
  video.srcObject = stream;
  video.hidden = false;
  await video.play();
  return () => {
    stream.getTracks().forEach(t => t.stop());
    video.srcObject = null;
    video.hidden = true;
  };
}
