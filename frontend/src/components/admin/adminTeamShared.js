/**
 * Shared permission catalog + helpers for the AdminTeam UI.
 * Kept in one tiny module so InviteForm, InviteBanner and AdminRow stay focused.
 */
export const PERMISSION_LABELS = {
  manage_events: "Manage events (create / delete tournaments)",
  manage_vendors: "Approve & revoke vendors",
  manage_listings: "Approve listings (grounds, coaches, etc.)",
  manage_bookings: "Confirm / reject ground bookings",
  manage_reviews: "Moderate reviews queue",
  manage_settings: "Edit site settings & About page",
  manage_companies: "Manage companies",
};

export const togglePerm = (list, p) =>
  list.includes(p) ? list.filter((x) => x !== p) : [...list, p];
