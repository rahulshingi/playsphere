import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import PeopleEditor from "@/components/admin/PeopleEditor";

export default function AboutTab({ about, setAbout, reload }) {
  const save = async () => { await api.patch("/about", about); toast.success("About page updated"); reload(); };
  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-3xl space-y-3">
      <div className="font-display tracking-wider text-2xl">ABOUT PAGE CONTENT</div>
      <p className="text-xs text-neutral-500 font-mono">
        Press <kbd className="px-1 py-0.5 bg-black/40 border border-white/10 rounded-sm">Enter</kbd> for a line break and a blank line for a new paragraph — both are preserved on /about.
      </p>
      <Label className="text-xs font-mono uppercase text-neutral-500">Company description</Label>
      <Textarea data-testid="about-desc" rows={6} value={about.company_description} onChange={(e) => setAbout({ ...about, company_description: e.target.value })} className="bg-black/40 border-white/10 text-white" />
      <Label className="text-xs font-mono uppercase text-neutral-500">Mission</Label>
      <Textarea data-testid="about-mission" rows={4} value={about.mission} onChange={(e) => setAbout({ ...about, mission: e.target.value })} className="bg-black/40 border-white/10 text-white" />
      <Label className="text-xs font-mono uppercase text-neutral-500">Vision</Label>
      <Textarea data-testid="about-vision" rows={4} value={about.vision} onChange={(e) => setAbout({ ...about, vision: e.target.value })} className="bg-black/40 border-white/10 text-white" />

      <PeopleEditor label="Founders" testid="founders" people={about.founders || []} onChange={(p) => setAbout({ ...about, founders: p })} />
      <PeopleEditor label="Directors" testid="directors" people={about.directors || []} onChange={(p) => setAbout({ ...about, directors: p })} />

      <Button data-testid="about-save" onClick={save} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save About page</Button>
    </div>
  );
}
