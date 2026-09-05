# ARGUS Project — Person D: Audience Experience (Web Design + Exhibition + QA + Content)

> **This is a no-code role.** You will design, write, test, and present — not write production code.
> Everything you design gets *implemented* by Person B (or with AI help). You own how it **looks, reads, and feels**; B owns how it **works**.

---

### 📌 About this document
This document summarizes **your part** of the ARGUS project.
- Contents: project intro → team roles → your scope → how you connect to the team → how to work in parallel → schedule → an AI prompt for you.
- **At the very bottom is your own "AI prompt" and how to use it** (register it as a Claude/ChatGPT *Project* instruction so you never have to paste the background again).

Read the whole thing first, then set up the prompt at the end in your own AI.

> 💡 **The details here are a starting point ("draft").** Layouts, wording, colors, and names are just examples. As long as the big direction holds (design the audience-facing experience + exhibition materials, hand specs to B, test the whole thing), feel free to propose something better.

---

### 1. Project introduction
**ARGUS** is an **AI companion robot** built on a six-legged robot (Freenove Big Hexapod + Raspberry Pi 5). It watches its surroundings with a camera, detects people and objects, can be followed from a dashboard, and can talk with you by voice.

**HEW version concept:** visitors watch the **live video (with AI-detection overlay)** on their phone, and **pay (tip) to make the robot perform actions or missions**. Every payment is stored in the database (required for HEW: "a web service where money moves"). No real money moves — it's simulated via Stripe test mode or mock data.

Three-layer architecture:
- **Locomotion layer:** official Freenove code (off-the-shelf, unmodified, assembled by the whole team)
- **AI layer (ours):** image recognition + voice dialogue
- **IoT layer (ours):** Flask backend + payment + web dashboard ← **the "web service where money moves" lives here**

---

### 2. Team roles (4 people)
- **Person A — Image recognition:** YOLO/OpenCV on Pi 5. Detects people/objects and sends them to the backend.
- **Person B — Backend + dashboard + payment:** Flask + SQLite. Receives/stores detections, takes payments and records transactions, turns payments into robot actions, serves the web pages.
- **Person C — Voice + integration (Nin / team leader):** voice dialogue with the robot, bridges both voice intent and paid actions to the locomotion layer, final integration. Holds the physical robot.
- **Person D — Audience Experience (= you):** designs the audience-facing web page, makes the exhibition/presentation materials, owns the audience-facing copy, and tests the whole system as the "audience."

The team runs as a **star centered on B (the backend)**:
- A (image) → sends detections **to B** (`POST /upload`)
- Visitors (web) → pay **to B** (`POST /pay`) → B records the transaction + queues the action
- C (voice/integration) → reads latest detections **from B** (`GET /events`) + pulls paid actions (`GET /commands`) → sends commands to locomotion
- **You (D)** → design what visitors see (implemented by B), and test the full loop end-to-end.
- **A and C never talk directly.** You (D) connect only through B and through the team leader — you never touch A's or C's code.

---

### 3. Your scope (no code required)

**① Audience-facing web design (design, not code)**
Design the public page that visitors see and tap:
- Live video area (with A's detection overlay)
- Tip / action buttons (e.g., ¥100 single action, ¥300 30-sec control, ¥500 "find X" mission)
- Recent transaction feed
- Tip ranking / "Today's Owner" board
- The overall near-future mission-HUD aesthetic

You deliver **mockups + assets + exact copy** (Figma, Canva, slides, or even hand sketches). B turns them into the real page. You review the result and request changes.

**② Exhibition & presentation materials**
This is a HEW exhibition piece and needs someone to *sell the concept*:
- HEW poster
- Slide deck for the presentation
- A ~1-minute live-demo script
- Booth signage explaining "pay to control the robot"
- A printed action/price menu card
- A QR-code standee that opens the web page

**③ Audience-facing content & copy**
- All button labels, price-menu wording, page headings, ranking framing
- (Optional) Draft ARGUS's spoken reply lines / personality for C's text-to-speech
- Propose the human-readable action names (e.g., "forward / bow / intimidate") — this feeds directly into the shared action-naming that the team must lock (see §6)

**④ QA / testing**
Be the "audience." Walk the whole loop — scan QR → watch video → pay → robot moves → see it appear in history/ranking — find what breaks, file clear bug reports, and keep a simple test checklist. This is especially valuable during the August integration.

**⑤ (Optional, if you have capacity) Coordination support for the leader**
Take meeting notes, and maintain the interface-contract / action-name table so nothing drifts between the three code modules. Directly lightens the leader's load.

**Deliverables:** page mockups + copy, poster + slides + demo script + signage + QR, a test checklist + bug reports.

---

### 4. How you connect to the team
- **You depend on B.** Your designs get implemented into B's public page; you test that same page. Agree a clean boundary with B: **B owns the endpoints and data; you own the layout, styling, and copy that sit on top.**
- **Content/naming that touches C or A** (spoken lines, action names, mission wording) goes **through B or through the leader**, never by editing their code.
- You are **deliberately off the critical path.** The guaranteed core (robot moves + payment is recorded) belongs to A/B/C. Your work is the high-visibility polish and the exhibition — a slip on your side never sinks the core demo.

---

### 5. Working in parallel (don't wait for hardware or anyone)
- You need **no robot and no finished backend** to start.
- Design the entire page **now**, from this spec plus a few lines of example data (B can give you a sample JSON, or just invent realistic numbers).
- Make **all** exhibition materials now — poster, slides, demo script, signage, price menu.
- Write **all** copy now.
- Only the live end-to-end QA waits for integration in August.

---

### 6. Schedule (summer sprint)
**Development period = summer break (7/24 → end of August). Hard deadline: end of August.**
- **Start now:** page mockups, price/action menu draft, poster/slide outline — all doable immediately on any laptop.
- **7/24 kickoff meeting (bring your drafts):** bring your first page mockup + draft price/action menu, so the team can lock the **action names** and page UX together with the interface contract. Your naming proposal is a real input to this meeting.
- **Mid–late August:** hardware assembly (whole team) + real-hardware integration + 3-module testing — you run acceptance passes here.
- **End of August:** finished, deadline.

---

## ▼ Setting up your AI (use the "Project" feature)

### So you don't paste the prompt every time
Both Claude and ChatGPT have a **Projects** feature: set the prompt once, and every conversation in that project automatically carries the background.

**Claude** (works on the free plan, up to 5 projects):
1. Left menu → "Projects" → "+ New Project"
2. Name it (e.g., `ARGUS Audience Experience`)
3. Paste the prompt below into the project's **instructions (custom instructions)**
4. (Optional) Upload this document into the project as knowledge
→ From then on, any chat in this project has the background automatically.

**ChatGPT** (free or paid):
1. Left menu → "Projects" → "New"
2. Name it
3. Top-right "…" → "Project settings" → paste the prompt into **instructions**
4. (Optional) Drag this document into a project chat to upload it
→ From then on, every chat in the project applies it automatically.

---

### Prompt to paste
```
You are an assistant helping me with the "Audience Experience" part of a team robotics project. I am NOT a programmer — I do design, writing, presentation, and testing. When you help me, give me designs, copy, materials, plans, and step-by-step non-code instructions. Do not expect me to write production code; if code is needed, produce something I can hand to my teammate, and explain it plainly.

[Project] ARGUS — an AI companion robot based on a Raspberry Pi 5 + Freenove six-legged robot. A 4-person team. Three-layer architecture (locomotion = off-the-shelf Freenove / AI layer = ours / IoT layer = ours). To fit the HEW theme "a web service where money moves," it becomes a "ticket-to-control AI companion robot": visitors pay (tip) to make the robot do actions/missions, and every transaction is stored in the DB. No real money moves — Stripe test mode or mock data.

[My role] Audience Experience (no code). I (1) design the visitor-facing web page (live video, tip/action buttons, transaction feed, tip ranking, a near-future mission-HUD look) as mockups + copy + assets and hand them to the backend teammate to implement; (2) make exhibition/presentation materials (poster, slide deck, ~1-min demo script, booth signage, printed price/action menu, QR standee); (3) own all audience-facing copy and propose human-readable action names; (4) test the whole system as the "audience" and file bug reports.

[Team structure] Star topology centered on the backend (Person B). Person A does image recognition and posts detections to B. Person B does the Flask+SQLite backend, payment, and web pages. Person C (the leader) does voice dialogue and final integration. I (D) depend only on B, and route anything touching A or C through B or the leader — I never edit their code.

[How I work] I don't need the robot or a finished backend to start. I design the page from a spec plus sample data, make all exhibition materials, and write all copy up front. Only live end-to-end testing waits for integration in August.

[My tools] Figma / Canva / Google Slides / PowerPoint for design and presentation; plain documents for copy and test checklists.
[Timeline] Finish during summer break (7/24 → end of August); deadline end of August; I can start anytime.

Based on this, help me with concrete deliverables and steps for: (1) a mockup + copy for the visitor-facing page, (2) the exhibition poster and slide deck, (3) a 1-minute live-demo script, (4) the price/action menu and button labels, and (5) a test checklist for the full "scan → watch → pay → robot moves → shows in history" loop. Start by suggesting what I should tackle first.

Note: the page layout, wording, prices, and action names above are just a starting point. As long as the big direction holds (design the audience experience + exhibition, hand specs to the backend teammate, test the whole thing), feel free to propose something better. Don't be constrained by the details.
```
