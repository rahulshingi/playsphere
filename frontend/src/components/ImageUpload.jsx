import { useRef, useState } from "react";
import api from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Upload, Link as LinkIcon } from "lucide-react";
import { toast } from "sonner";
import { compressImage } from "@/lib/compressImage";
import { resolveImageUrl, imageOnError } from "@/lib/imageUrl";

/**
 * Combined image input: paste a URL OR upload a file.
 * Files are compressed client-side (≤1280×1280, JPEG q≥0.5, ≤500KB) and the server
 * further re-compresses + stores the bytes in MongoDB — so uploaded images survive
 * container restarts and redeploys. We store the RELATIVE URL returned by the API
 * so the same DB value works in preview AND production.
 */
export default function ImageUpload({ value, onChange, placeholder = "https://… or upload", testid = "image-upload" }) {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);

  const onPick = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const compressed = await compressImage(file).catch(() => file);
      const fd = new FormData();
      fd.append("file", compressed);
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      // Store the RELATIVE path returned by the API — resolveImageUrl makes it absolute at render time.
      onChange(data.url);
      const kb = Math.round((data.size || compressed.size) / 1024);
      toast.success(`Image uploaded · ${kb} KB`);
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex gap-2 items-center">
      <div className="relative flex-1">
        <LinkIcon className="absolute left-3 top-2.5 w-3.5 h-3.5 text-neutral-500" />
        <Input data-testid={`${testid}-url`} value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="pl-8 bg-black/40 border-white/10 text-white" />
      </div>
      <input ref={ref} type="file" accept="image/*" data-testid={`${testid}-file`} onChange={(e) => onPick(e.target.files?.[0])} className="hidden" />
      <Button type="button" size="sm" variant="outline" data-testid={`${testid}-browse`} disabled={busy}
              onClick={() => ref.current?.click()}
              className="border-white/10 bg-transparent text-white rounded-sm h-9 px-3 shrink-0">
        <Upload className="w-3.5 h-3.5 mr-1" /> {busy ? "Uploading…" : "Upload"}
      </Button>
      {value && <img src={resolveImageUrl(value)} onError={imageOnError} alt="" className="w-9 h-9 object-cover rounded-sm border border-white/10" />}
    </div>
  );
}
