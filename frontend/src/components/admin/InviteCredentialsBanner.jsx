import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Copy } from "lucide-react";

export default function InviteCredentialsBanner({ invite, onDismiss }) {
  const copy = () => {
    const text = `Welcome to Kreeda Nation HQ.\n\nLogin: ${window.location.origin}${invite.login_url}\nEmail: ${invite.email}\nTemporary password: ${invite.temp_password}\n\nPlease change your password after first sign-in.`;
    navigator.clipboard?.writeText(text);
    toast.success("Copied invite to clipboard");
  };
  return (
    <div data-testid="team-invite-banner" className="border border-[#84CC16]/40 rounded-sm bg-[#84CC16]/10 p-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#84CC16]">/ Invite created</div>
          <div className="text-sm text-neutral-100 mt-2">
            <div><strong>Email:</strong> {invite.email}</div>
            <div><strong>Password:</strong> <code className="bg-black/40 px-2 py-0.5 rounded-sm">{invite.temp_password}</code></div>
            <div><strong>Sign in:</strong> {window.location.origin}{invite.login_url}</div>
          </div>
          <p className="text-xs text-neutral-300 mt-2">{invite.note}</p>
        </div>
        <div className="flex flex-col gap-2 shrink-0">
          <Button size="sm" variant="ghost" onClick={copy} data-testid="team-invite-copy" className="text-[#84CC16]">
            <Copy className="w-4 h-4 mr-1" /> Copy
          </Button>
          <Button size="sm" variant="ghost" onClick={onDismiss} className="text-neutral-400">Dismiss</Button>
        </div>
      </div>
    </div>
  );
}
