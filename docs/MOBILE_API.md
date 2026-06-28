# Kreeda Nation — Mobile API Reference (Flutter / Android / iOS)

**Base URL (production):** `https://kreedanation.com/api`
**Base URL (preview / dev):** read from your env (the same backend, different host)
**Content-Type:** `application/json` everywhere except `multipart/form-data` for file uploads.
**Auth:** JWT bearer token in `Authorization: Bearer <token>` header.
**WebSocket:** `wss://kreedanation.com/api/ws` (for live scores)

---

## 1) Setup in Flutter

`pubspec.yaml`
```yaml
dependencies:
  dio: ^5.4.0
  flutter_secure_storage: ^9.0.0
  web_socket_channel: ^2.4.0
  image_picker: ^1.0.7
```

`lib/api_client.dart`
```dart
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiClient {
  static const baseUrl = 'https://kreedanation.com/api';
  static final _storage = const FlutterSecureStorage();
  static final dio = Dio(BaseOptions(
    baseUrl: baseUrl,
    connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 30),
  ))..interceptors.add(InterceptorsWrapper(
      onRequest: (opts, handler) async {
        final token = await _storage.read(key: 'kn_token');
        if (token != null) opts.headers['Authorization'] = 'Bearer $token';
        handler.next(opts);
      },
    ));

  static Future<void> saveToken(String t) => _storage.write(key: 'kn_token', value: t);
  static Future<void> clear() => _storage.delete(key: 'kn_token');
}
```

---

## 2) Authentication

### 2.1 Universal login (every role)
`POST /auth/login`
```json
{ "email": "user@example.com", "password": "secret" }
```
**Response 200**
```json
{
  "token": "<jwt>",
  "user": {
    "id": "uuid", "email": "user@example.com", "name": "Ravi",
    "role": "player",          // platform_admin | company_admin | organiser | vendor | player | sponsor | scorer
    "company_id": "uuid|null"
  }
}
```
**Errors:** `401` invalid creds · `423` account disabled · `429` brute-force throttle.

```dart
Future<void> login(String email, String pwd) async {
  final r = await ApiClient.dio.post('/auth/login', data: {'email': email, 'password': pwd});
  await ApiClient.saveToken(r.data['token']);
}
```

### 2.2 Current user
`GET /auth/me` → returns the same `user` block as above. Use this to bootstrap profile after app launch.

### 2.3 Player signup (mobile-first, OTP via SMS deferred → email today)
```
POST /players/signup/request-otp   {"mobile":"+91...", "email":"..."}
POST /players/signup               {"mobile":"...", "email":"...", "name":"...", "password":"...", "otp":"123456"}
```

### 2.4 Company / Organiser signup
```
POST /companies/signup/request-otp {"admin_email":"...", "company_name":"..."}
POST /companies/signup             {"company_name","admin_name","admin_email","admin_password","contact_phone","otp","address_line","area","city","state","pincode"}

POST /organisers/signup/request-otp {"email":"..."}
POST /organisers/signup            {"company_name","admin_name","admin_email","admin_password","otp","address_line","area","city","state","pincode"}
```

### 2.5 Forgot / reset password
```
POST /auth/forgot-password  {"email": "..."}
POST /auth/reset-password   {"token":"<from email>", "password":"new"}
```

---

## 3) Events

### 3.1 List public events
`GET /events?scope=mine` (omit `scope` for all approved events)
```json
[{ "id":"uuid","name":"...","sport":"cricket","format":"knockout","venue":"...",
   "start_date":"2026-03-15","banner_url":"...","approval_status":"approved",
   "company_id":"uuid", "stream_url":"https://...","accept_sponsorships":true }]
```

### 3.2 Event detail
`GET /events/{event_id}` → full event object (including `sponsorship_opportunities`).

### 3.3 Create event (HR / organiser / platform_admin)
`POST /events` body matches `Event` shape (name, sport, format, event_type, venue, dates, banner, etc.). Organiser-created events come back with `approval_status="pending_organiser_ack"`.

### 3.4 Organiser-event approval workflow
```
POST /events/{id}/acknowledge-instructions      // organiser submits for admin review
GET  /events/pending-approval                   // platform admin inbox
POST /events/{id}/approve                       // platform admin approves
POST /events/{id}/reject  {"reason":"..."}      // platform admin rejects
```

### 3.5 Teams + fixtures + standings
```
GET  /teams?event_id={id}
POST /teams                                     {"event_id","name","short_name","color","company_id?"}
GET  /events/{id}/fixtures
GET  /events/{id}/standings
POST /events/{id}/generate-fixtures             // locked once any fixture is live/completed
```

### 3.6 Live score updates (used by scorers + HRs)
```
POST /fixtures/{fixture_id}/init-score
PATCH /fixtures/{fixture_id}                    {"score":{...},"status":"live","winner_id":"uuid?"}
```
Sport-specific score shapes:
- **Cricket:** see §6
- **Football:** `{team_a:{goals:0}, team_b:{goals:0}}`
- **Basketball:** `{team_a:{points:0,q:1}, team_b:{points:0,q:1}}`
- **Badminton / TT / Volleyball:** `{team_a:{sets:[s1,s2,s3]}, team_b:{...}}`
- **Chess / quiz:** `{team_a:{points:0}, team_b:{points:0}}`
- **Hackathon / fallback:** `{team_a:{score:0}, team_b:{score:0}}`

### 3.7 Scorer invitations
```
GET    /events/{event_id}/scorers
POST   /events/{event_id}/scorers   {"email","name?","fixture_ids":[]}  // [] = all fixtures
DELETE /events/{event_id}/scorers/{assignment_id}
GET    /scorers/me/events                                                 // scorer's own assignments
```

---

## 4) Vendor Marketplace

```
GET  /vendor-listings?city=Pune&sport=cricket    // list with rating + cheapest_membership attached
GET  /vendor-listings/{listing_id}               // detail incl. cheapest_membership
GET  /venues/suggest?sport=cricket&q=kharadi     // searchable picker — see §8 too
POST /bookings                                   {"listing_id","start_at","end_at","slot_count"}
GET  /bookings                                   // mine
PATCH /bookings/{id}                             {"status":"cancelled" | ...}
GET  /vendor-listings/{listing_id}/blocks        // schedule/blocked time slots
```

---

## 5) Player profiles

```
GET   /players/me
PATCH /players/me                  // multi-sport: interested_sports[], sport_profiles{}, lifetime_stats{}
GET   /players/profiles?sport=cricket&role=batsman&city=Pune
GET   /players/profiles/{profile_id}    // increments view_count
```

---

## 6) Cricket live scoring

All under `/fixtures/{fid}/cricket/...`. Auth: only the event manager OR an assigned scorer. Endpoints (`POST` unless noted):
```
POST /cricket/setup                  // toss, playing XI, format (T20/ODI/Test), batting/bowling order
POST /cricket/ball                   // body { runs, extras{wide,no_ball,bye,leg_bye}, wicket{...}, batsman_id, bowler_id }
POST /cricket/undo                   // undo last ball
POST /cricket/wicket                 // explicit wicket entry
POST /cricket/end-over
POST /cricket/innings-break
POST /cricket/end-match
GET  /fixtures/{fid}                 // re-fetch the latest score doc
```
Cricket score doc shape is large — fetch and pass through as-is to your render layer.

---

## 7) WebSocket — live updates

Connect once on app start, multiplex per-fixture by filtering messages client-side.
```dart
final ch = WebSocketChannel.connect(Uri.parse('wss://kreedanation.com/api/ws'));
ch.stream.listen((raw) {
  final msg = jsonDecode(raw);
  // { type:"fixture_update", event_id, fixture }
  // { type:"booking_update", booking_id, ... }
});
```
Reconnect with exponential backoff on close.

---

## 8) Sponsorship marketplace

```
GET  /sponsorship-marketplace                 // public listings (organiser-published slots)
GET  /events/{id}/sponsorships/interests      // organiser view
POST /events/{id}/sponsorships/{slot_id}/interest        // sponsor expresses interest
POST /events/{id}/sponsorships/{slot_id}/award           // organiser awards slot to sponsor
GET  /sponsors/me                                         // sponsor profile
PATCH /sponsors/me                                        // brand, industry, logo_url, target_locations[]
GET  /sponsors                                            // public sponsor directory
```

---

## 9) Memberships (Phase 1 — vendor-defined; purchase coming in Phase 2)

```
GET    /memberships/mine                          // vendor — their plans
POST   /memberships/mine                          // vendor — create plan
PATCH  /memberships/mine/{plan_id}
DELETE /memberships/mine/{plan_id}

GET    /memberships/vendor/{vendor_id}            // public
GET    /memberships/listing/{listing_id}          // public — plans usable at this listing
```
`MembershipPlan` shape: `{ id, vendor_id, listing_ids[], title, description, plan_type, sports[], price, currency, duration_days, max_bookings, slot_days_of_week[], slot_start_time, slot_end_time, advance_booking_hours, active, paused }`. `plan_type ∈ { monthly | daily_pass | gym | weekend | fixed_slot | open }`.

---

## 10) File / image uploads

`POST /upload` — multipart `image` field. Returns `{ id, url }`. Images are stored in MongoDB and served from `/uploads/{id}`. Use these URLs in `photo_url`, `banner_url`, `logo_url`, etc.

```dart
final form = FormData.fromMap({
  'image': await MultipartFile.fromFile(path, filename: 'photo.jpg'),
});
final r = await ApiClient.dio.post('/upload', data: form);
final url = r.data['url'];
```

---

## 11) Settings, contact, misc

```
GET  /settings                       // public site settings (incl. organiser_event_instructions)
POST /contact                        // public contact form { name,email,phone,message }
GET  /contact-messages               // platform admin inbox (auth required)
PATCH /contact-messages/{id}         // { read:true } or { archived:true }
DELETE /contact-messages/{id}        // must be read first
```

Admin user/account management:
```
GET   /admin/users?role=player       // platform admin
PATCH /admin/users/{user_id}/disabled  { "disabled": true }
GET   /admin/players/{id}/detail       // full enrichment (teams, events, reviews)
GET   /admin/vendors/{id}/detail
GET   /admin/companies/{id}/detail
```

---

## 12) Errors — Flutter-friendly shape

All errors return `{ "detail": "human readable" }` with the right HTTP status (`400` validation, `401` unauth, `403` forbidden, `404` not found, `429` throttled, `500` server). Wrap your dio calls:

```dart
try {
  final r = await ApiClient.dio.get('/events');
} on DioException catch (e) {
  final msg = e.response?.data is Map ? e.response!.data['detail'] : e.message;
  // show snackbar with msg
}
```

---

## 13) Push notifications (future / out-of-scope today)

Push is not wired in the backend yet. For now, mobile apps should poll `GET /events/pending-approval`, `GET /scorers/me/events`, etc. on tab focus, and rely on the WebSocket for live scores.

---

## 14) Production checklist for mobile release

- [ ] App-store binary signs in against `https://kreedanation.com/api` (not preview URL).
- [ ] Store JWT in `flutter_secure_storage` (Keychain on iOS, EncryptedSharedPreferences on Android).
- [ ] Handle 401 globally → clear token, route to login.
- [ ] Reconnect WebSocket on app resume.
- [ ] Use `path_provider` to cache uploaded images locally before sending so large photos don't OOM on Android.
- [ ] Deep-links: `kreedanation://events/{id}`, `kreedanation://fixtures/{id}` — agree on URL scheme with backend if needed.
- [ ] Test on a real iPhone for camera + photo permissions (image_picker).
- [ ] Razorpay SDK will be needed once Phase 2 memberships ship — keep it gated behind a feature flag.

---

_Last updated: based on the current backend in `/app/backend/`. If any endpoint listed here returns 404, ping the platform team; the route map evolves._
