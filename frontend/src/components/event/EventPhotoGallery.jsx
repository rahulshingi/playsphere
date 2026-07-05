import { useRef, useState } from "react";
import api from "@/lib/api";
import { compressImage } from "@/lib/compressImage";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { toast } from "sonner";
import { X, Camera, Upload } from "lucide-react";
import { resolveImageUrl } from "@/lib/imageUrl";

/**
 * Post-tournament photo gallery. Anyone can view; only the event creator +
 * platform admins can upload / delete. Tap a thumbnail to open the lightbox.
 */
export default function EventPhotoGallery({ event, canManage, onChange }) {
  const [uploading, setUploading] = useState(false);
  const [lightbox, setLightbox] = useState(null);
  const fileRef = useRef(null);
  const photos = event.photos || [];

  const addPhoto = async (url) => {
    if (!url) return;
    try {
      const { data } = await api.post(`/events/${event.id}/photos`, { url });
      onChange?.(data.photos);
      toast.success("Photo added");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Add failed");
    }
  };

  const onPickFile = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const compressed = await compressImage(file);
      const fd = new FormData();
      fd.append("file", compressed, file.name);
      const { data } = await api.post("/upload", fd);
      await addPhoto(data.url);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removePhoto = async (url) => {
    if (!window.confirm("Remove this photo?")) return;
    try {
      const { data } = await api.delete(`/events/${event.id}/photos`, { params: { url } });
      onChange?.(data.photos);
      toast.success("Removed");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  if (!canManage && photos.length === 0) return null;

  return (
    <section data-testid="event-photo-gallery" className="mt-8 border border-white/10 rounded-sm bg-[#0f0f0f] p-5">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Event gallery</div>
          <div className="font-display tracking-wider text-2xl mt-1">PHOTOS ({photos.length})</div>
        </div>
        {canManage && (
          <div className="flex items-center gap-2">
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              data-testid="gallery-file-input"
              onChange={(e) => onPickFile(e.target.files?.[0])}
              className="hidden"
            />
            <Button
              type="button"
              data-testid="gallery-upload-btn"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"
            >
              <Upload className="w-4 h-4 mr-1.5" /> {uploading ? "Uploading…" : "Upload photo"}
            </Button>
          </div>
        )}
      </div>

      {photos.length === 0 ? (
        <div className="text-center py-10 text-sm text-neutral-500 border border-dashed border-white/10 rounded-sm">
          <Camera className="w-6 h-6 mx-auto mb-2 opacity-40" />
          No photos yet. {canManage && "Tap “Upload photo” above to add moments from the tournament."}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
          {photos.map((url) => (
            <div key={url} className="relative group aspect-square overflow-hidden rounded-sm border border-white/10 bg-black/40" data-testid="gallery-photo">
              <button type="button" onClick={() => setLightbox(url)} className="block w-full h-full">
                <img src={resolveImageUrl(url)} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
              </button>
              {canManage && (
                <Button
                  size="icon"
                  variant="ghost"
                  data-testid="gallery-delete"
                  onClick={() => removePhoto(url)}
                  className="absolute top-1 right-1 h-6 w-6 bg-black/70 hover:bg-[#FF3B30] rounded-sm opacity-0 group-hover:opacity-100 transition"
                >
                  <X className="w-3 h-3 text-white" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      <Dialog open={!!lightbox} onOpenChange={(v) => !v && setLightbox(null)}>
        <DialogContent className="max-w-4xl bg-black border-white/10 p-2">
          {lightbox && <img src={resolveImageUrl(lightbox)} alt="" className="w-full max-h-[80vh] object-contain" />}
        </DialogContent>
      </Dialog>
    </section>
  );
}
