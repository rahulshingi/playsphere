// Role -> manual PDF mapping.
// Used by the top Nav to surface a single, role-appropriate guide to logged-in users.
export const ROLE_GUIDE = {
  platform_admin: {
    label: "Admin guide",
    href: "/manuals/kreeda-nation-platform-admin-manual.pdf",
    testid: "nav-guide-admin",
  },
  admin: {
    label: "Admin guide",
    href: "/manuals/kreeda-nation-platform-admin-manual.pdf",
    testid: "nav-guide-admin",
  },
  company_admin: {
    label: "HR guide",
    href: "/manuals/kreeda-nation-company-manual.pdf",
    testid: "nav-guide-company",
  },
  organiser: {
    label: "Organiser guide",
    href: "/manuals/kreeda-nation-organiser-manual.pdf",
    testid: "nav-guide-organiser",
  },
  vendor: {
    label: "Vendor guide",
    href: "/manuals/kreeda-nation-vendor-manual.pdf",
    testid: "nav-guide-vendor",
  },
  player: {
    label: "Player guide",
    href: "/manuals/kreeda-nation-player-manual.pdf",
    testid: "nav-guide-player",
  },
  sponsor: {
    label: "Sponsor guide",
    href: "/manuals/kreeda-nation-sponsor-manual.pdf",
    testid: "nav-guide-sponsor",
  },
  scorer: {
    label: "Scorer guide",
    href: "/manuals/kreeda-nation-scorer-manual.pdf",
    testid: "nav-guide-scorer",
  },
};

export const getRoleGuide = (role) => ROLE_GUIDE[role] || null;
