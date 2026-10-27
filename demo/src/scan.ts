import { $, API, errorText, getJSON } from "./util";

type ScanResult = { lesson_id: string | null; confidence: number; decision: "auto" | "confirm" | "rescan" };

let stream: MediaStream | null = null;

function setScanStatus(text: string, cls = "") {
  const el = $("scan-status");
  el.textContent = text;
  el.className = cls;
}

async function openScan() {
  $("scan").hidden = false;
  $("scan-open").hidden = true;
  setScanStatus("Point the camera at a lesson page");

  const video = $<HTMLVideoElement>("scan-video");
  const capture = $<HTMLButtonElement>("scan-capture");
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
    video.srcObject = stream;
    await video.play();
    capture.hidden = false;
  } catch {
    capture.hidden = true;
    setScanStatus("Camera not available here. Use “Upload photo” instead.", "error");
  }
}

function closeScan() {
  stream?.getTracks().forEach(t => t.stop());
  stream = null;
  $<HTMLVideoElement>("scan-video").srcObject = null;
  $("scan").hidden = true;
}

function captureFrame(): Promise<Blob> {
  const video = $<HTMLVideoElement>("scan-video");
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d")!.drawImage(video, 0, 0);

  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => {
      if (blob) resolve(blob);
      else reject(new Error("capture failed"));
    }, "image/jpeg", 0.92);
  });
}

function openLesson(lessonId: string) {
  location.search = `?lesson=${encodeURIComponent(lessonId)}`;
}

async function recognize(image: Blob) {
  const openBtn = $<HTMLButtonElement>("scan-open");
  openBtn.hidden = true;
  setScanStatus("Recognizing…");

  let result: ScanResult;
  try {
    const form = new FormData();
    form.append("file", image, "scan.jpg");
    const res = await fetch(`${API}/api/v1/recognition/page`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    result = await res.json();
  } catch (e) {
    setScanStatus(`Scan failed (${errorText(e)})`, "error");
    return;
  }

  const lessonId = result.lesson_id;
  if (!lessonId || result.decision === "rescan") {
    setScanStatus("No lesson recognized. Fill the frame with the figure and try again.", "error");
    return;
  }

  if (result.decision === "auto") {
    setScanStatus(`Found ${lessonId}. Opening…`, "ok");
    closeScan();
    openLesson(lessonId);
    return;
  }

  let title = lessonId;
  try {
    title = (await getJSON<{ title: string }>(`${API}/api/v1/lessons/${lessonId}`)).title;
  } catch { }
  setScanStatus(`Is this “${title}”?`);
  openBtn.onclick = () => {
    closeScan();
    openLesson(lessonId);
  };
  openBtn.hidden = false;
}

export function setupScan() {
  $("scan-btn").onclick = openScan;
  $("scan-close").onclick = closeScan;
  $("scan-capture").onclick = async () => recognize(await captureFrame());

  const fileInput = $<HTMLInputElement>("scan-file");
  fileInput.onchange = () => {
    const file = fileInput.files?.[0];
    if (file) recognize(file);
    fileInput.value = "";
  };
}
