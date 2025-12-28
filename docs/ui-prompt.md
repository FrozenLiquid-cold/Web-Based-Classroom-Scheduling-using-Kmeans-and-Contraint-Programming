You are building the frontend UI for “JRMSU K‑MEANS AND CONSTRAINT PROGRAMMING CLASSROOM SCHEDULING SYSTEM”. Recreate the exact structure and layout from the provided prototype (Screens 1–12). No backend. Use React (with React Router) or plain PHP templates; Tailwind or CSS is fine. Persist mock data with localStorage.

Global
- Canvas: 1366×768 baseline, full-bleed light tech-circuit background image with subtle blur/overlay.
- Primary colors: Deep Navy #1E2567 (headers/sidebar), Royal Blue #2F3FA5 (buttons/accents), Gold #C9A54A (titles), Light Gray #F2F4F8 (inputs).
- Typography: Similar to Montserrat/Poppins (bold headings, medium labels). Letter-spacing slightly increased for headers. All-caps for section titles.
- Card style: White cards with 16–20px radius, soft shadow (0 10px 20px rgba(0,0,0,0.15)).
- Tables: Dark navy header row (white text), zebra rows, compact padding. “Action” column with circular icon buttons (edit: blue, delete: red).
- Inputs: Rounded 24px height, inset shadow, left-aligned labels. Search boxes show “Search: <Label>”.
- Icons: Use a circular user silhouette top-right; edit (pen), delete (trash), add (plus-in-square).
- Logo: Center/top placements use `jrmsu-logo.png` (transparent bg).

Routing (no-auth backend; use mock auth)
- /  Landing
- /login/registrar  Registrar Login
- /r/*  Registrar area (protected by mock session)
  - dashboard, college, course, instructor, day, subject, room, curriculum, schedule, user (notifications/about/account)

Screen 1 – Landing
- Centered layout with JRMSU logo above a gold “JOSE RIZAL MEMORIAL STATE UNIVERSITY” title.
- Subtitle: “K-MEANS AND CONSTRAINT PROGRAMMING CLASSROOM SCHEDULING SYSTEM”.
- Three large frosted tiles spaced horizontally labeled A (Admin), I (Instructor), R (Registrar). Only Registrar is clickable (hover scale + glow).
- On click Registrar → navigate to /login/registrar.
- Footer line “Develop by: … © 2025” centered, small.

Screen 2 – Registrar Login
- Glassmorphism card centered; top shows JRMSU logo, system title (two-line), and “REGISTRAR” in gold.
- Two inputs (Username, Password) with left icons; password has right eye toggle.
- Primary “Login” button in rounded pill (Royal Blue) with white text and slight inner glow.
- On submit, validate non-empty and if user==registrar & pass==1234 set mock session to localStorage then go /r/dashboard.

Registrar Layout (Screens 3+)
- Left fixed sidebar (Deep Navy), 260px wide, logo at top, product label “CLASS - HCP”.
- Nav items stacked: Dashboard, College, Course, Instructor, Day, Subject, Room, Curriculum, Schedule. Active item has lighter navy highlight.
- Right main content panel uses the circuit background, inner content with generous padding and a centered page title in all caps.
- Top-right user avatar with “Users” label. Clicking opens the user area (/r/user) with tabs.

Screen 3 – Dashboard
- Center large JRMSU logo with the gold university title and two-line system subtitle.
- No widgets, just hero center.

Screen 4 – College
- Page title “COLLEGE”, search box prefix “Search: College”.
- Card with table: columns [No., Code, Description, Action].
- Top-right “Add College” button (plus-in-square). Opens modal form (Code, Description) with Save/Cancel; validate required, unique code; persist to localStorage.
- Action icons: edit and delete (with confirm).

Screen 5 – Course
- Similar layout. Columns [No., College, Code, Description, Action].
- Add/Edit modal: select College, Code, Description.

Screen 6 – Instructor
- Columns [No., Instructor, Action]; Add/Edit modal with First Name, Middle (opt), Last Name.

Screen 7 – Day
- Columns [No., Day, Action]; Days like F, M-W, W, T-TH, SAT, SUN. Add/Edit modal single text or preset select.

Screen 8 – Subject
- Columns [No., Code, Description, Type, Unit, Action]. Type is LEC/LAB. Units numeric.
- Add/Edit modal: Code, Description, Type select, Units number.

Screen 9 – Room
- Columns [No., Room Name, Type, Action]. Type: LEC/LAB.
- Add/Edit modal: Name, Type.

Screen 10 – Schedule
- Title “SCHEDULE”. Filter row: Course (select), Year Level (1st–4th), Semester (1st/2nd). To the right: buttons “Regenerate” (red outline) and “Load Schedule” (green).
- Table columns: [No., Code, Description, Type, Unit, Day, Room, Time, Instructor].
- “Regenerate” runs a greedy in-browser generator:
  - Time blocks: 7:30–9:00, 9:00–10:30, 10:30–12:00, 1:00–2:30, 2:30–4:00, 4:00–5:30.
  - Ensure no instructor or room conflicts within the same slot.
  - Prefer LAB rooms for LAB subjects; otherwise LEC rooms.
  - Save current view as last schedule for the selected Course/Year/Sem in localStorage.
- “Load Schedule” restores last saved for the selected filters.

Screen 11 – Curriculum
- Title “CURRICULUM”; three selectors (Course, Semester, Year Level) arranged as shown. Content area may be empty or simple list placeholder.

Screens 12 / 12.1 – User Area
- Sidebar avatar large with username label.
- Table of notifications with columns [Date & Time, Message] similar styling to tables.
- About and Log Out options present. Log Out clears mock session and routes to /login/registrar.

Responsiveness
- Target desktop first (1366×768), allow down to 1024px by reducing paddings, wrapping filter controls.
- Keep proportions (tile sizes, table density) to match prototype feel.

Mock Data & Persistence
- Seed example Colleges, Courses, Instructors, Days, Subjects, Rooms on first load.
- localStorage keys: jrmsu.college, jrmsu.course, jrmsu.instructor, jrmsu.day, jrmsu.subject, jrmsu.room, jrmsu.schedule.<course>.<year>.<sem>, jrmsu.session.

Accessibility & Polish
- Focus outlines visible, buttons have hover/active states, icons have aria-labels.
- Use consistent spacing scale (4/8/12/16/24).

