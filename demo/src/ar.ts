export type ARMode = "webxr" | "native" | "pseudo" | "none";

type XRSystem = { isSessionSupported?: (mode: string) => Promise<boolean> };

export async function bestARMode(mv: { canActivateAR?: boolean } | null): Promise<ARMode> {
  const xr = (navigator as Navigator & { xr?: XRSystem }).xr;
  if (xr?.isSessionSupported) {
    const supported = await xr.isSessionSupported("immersive-ar").catch(() => false);
    if (supported) return "webxr";
  }
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
