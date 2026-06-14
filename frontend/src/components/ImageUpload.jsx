import { useRef, useState } from "react";
import api from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Upload, Link as LinkIcon } from "lucide-react";
import { toast } from "sonner";

/**
 * Combined image input: paste a URL OR upload a file.
 * Calls `onChange(url)` whenever the resolved image URL changes.
 * Returns the FULL absolute URL for uploads (prefixed with REACT_APP_BACKEND_URL).
 */
export default function ImageUpload({ value, onChange, placeholder = "https://… or upload", testid = "image-upload" }) {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);

  const onPick = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      // Backend returns a path like /api/uploads/<name>; turn into absolute URL.
      const abs = `${process.env.REACT_APP_BACKEND_URL}${data.url}`;
      onChange(abs);
      toast.success("Image uploaded");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
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
      {value && <img src={value} alt="" className="w-9 h-9 object-cover rounded-sm border border-white/10" />}
    </div>
  );
}
