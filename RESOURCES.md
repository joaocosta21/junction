# Junction 2026 — Developer Tools, Credits and Assets

> Listed as "Developer Tools and Assets" in the Junction app. **The listing showed `Status: Closed` with a countdown (T−16:03:29)** — some claims may have a deadline, so claim anything we might use **immediately** rather than when we need it.

Several entries here correspond to challenges already documented in this repo; this file covers the **credits and assets** side, including resources with no challenge attached.

## Compute and model credits
| Provider | Amount | Notes |
|---|---|---|
| **Verda** | **€200** | Full-stack AI cloud: GPU compute + inference API. Sign up to Verda Console → submit claim form → share with team per their docs. **Largest single credit allowance.** |
| **Modal** | **$100 per participant** | CPUs/GPUs up to B300, per-second billing, scale to zero. `modal deploy` → public URL. Modal Dojo for fine-tuning/RL. See [MODAL-CHALLENGE.md](MODAL-CHALLENGE.md) |
| **OpenAI** | **$100 per participant** | Codex credits + OpenAI developer tools |
| **Google Gemini** | credits | Eligible participants; up to 400 teams. See [GOOGLE-CHALLENGE.md](GOOGLE-CHALLENGE.md) |
| **Anthropic** | **$20 per participant** | Claude API credits |
| **Featherless** | **$50 API credits** | Open-weight model catalogue, via Junction coupon. **Plus bare-metal GPU credits for *selected* teams** (fine-tuning, large-scale embedding generation) — ask |
| **CRACI** | **€1,000 per team** | CI/CD build minutes, but usable for "any compute need". Needs a Junction invite code from #craci on Discord or their booth (3rd floor, next to the stage) |
| **Aiven** | **$50** | Postgres, Valkey, Kafka, ClickHouse, OpenSearch, Runtime. See [AIVEN-CHALLENGE.md](AIVEN-CHALLENGE.md) |

## Web data APIs
| Provider | Amount | Notes |
|---|---|---|
| **Context.dev** | **50,000 credits, no expiry** | No credit card. 50 concurrent requests. See [CONTEXTDEV-TECH-CHALLENGE.md](CONTEXTDEV-TECH-CHALLENGE.md) |
| **Exa** | **$50 per participant** | Search + Contents API, Websets, Monitors, MCP. See [EXA-CHALLENGE.md](EXA-CHALLENGE.md) |
| **Oxylabs** | first month free on $500 plan | Code `JUNCTION2026`. **⚠️ Credit card required; MUST cancel after use.** See [OXYLABS-CHALLENGE.md](OXYLABS-CHALLENGE.md) |

## Data storage and datasets — IronShard
**Cloud object storage built for developers and AI agents.** Relevant beyond storage:
- **Challenge datasets are preloaded into read-only IronShard buckets** where applicable — this may be the fastest route to several challenges' data
- **Zero-copy bucket forking** — instantly create a writable branch of a challenge dataset without duplicating it
- Accessible via **MCP** (for AI agents) and **S3-compatible API**
- **Use it to submit large artifacts:** trained models or datasets too big for GitHub's 100 MiB/file limit. Include bucket and object references in the submission; **judges get read access**

## Hardware — Junction Hardware Lab, 5th floor
Booking/pickup instructions: https://2026.hackjunction.com/hardware

### Arduino
**Arduino App Lab + Arduino UNO Q** — Edge AI / Physical AI prototypes, usable for **any** Junction challenge. Mentors on site. Pickup at the Arduino booth, 5th floor.
Kit contents: Arduino UNO Q (2 GB RAM, 16 GB eMMC) · USB-C cable · 8-in-1 USB-C hub · 45W PSU · **USB camera** · **Modulino Buzzer, Knob and Thermo sensors**
Software: Arduino App Lab (bring a laptop with it installed)

### Wendy
Makes building for **robots, drones and edge AI devices** as easy as a phone app. Plug in a Jetson, Raspberry Pi, ESP32 or Arduino, run `wendy run`, app is live on the device. Open source; Python, Swift, Rust, ROS. **Simulator available if no hardware.**

### Atech
Snap-together ESP32 modules + AI firmware generation. See [ATECH-CHALLENGE.md](ATECH-CHALLENGE.md). **First come, first served.**

## Robotics / CV platforms
- **Qualia** (Copenhagen) — robot learning data curation. Upload episodes (SO-101 arms, Rokoko mocap), auto-flag failed takes and timing issues, curate versioned datasets, export and train (e.g. pi0.5 with LeRobot).
- **Scailab / Scaipipe** — computer vision model pipeline: import and annotate images, **generate labelled synthetic training data from 3D scenes** in a visual node editor, train/evaluate detection, segmentation and tracking. **Runs in browser, no GPU needed. Built-in MCP server so Claude can drive the pipeline.**

## Other
- **MariaDB** — open to every team, whichever challenge. They want "the most interesting use of the database itself — a schema that solves something neatly, a query that does more than you would expect." Mention MariaDB in the submission and work gets **published and credited on mariadb.org**. See [MARIADB-CHALLENGE.md](MARIADB-CHALLENGE.md)
- **Cloudinary** — image/video transform, optimize, deliver. **⚠️ Separate submission form required.** See [CLOUDINARY-CHALLENGE.md](CLOUDINARY-CHALLENGE.md)

## What to claim right now, regardless of challenge choice
Total free compute available to a team of 4 is substantial — roughly **€200 Verda + $400 Modal + $400 OpenAI + $80 Claude + €1,000 CRACI + $200 Featherless + $50 Aiven**, plus web-data credits. Claiming is minutes of work and several have deadlines.

Priority:
1. **Modal** ($100 × 4 = $400) — gives us the public demo URL via `modal deploy`, useful whatever we build
2. **Verda** (€200) — largest single allowance, needs a form submitted
3. **Claude + OpenAI + Gemini** — model credits for whatever the build needs
4. **Featherless** — ask about the selected-team bare-metal GPU credits if we fine-tune
5. **Hardware lab (5th floor)** — if hardware is in play at all, go early; Arduino and Atech kits are finite

## Implications for our shortlist
- **Scaipipe's synthetic labelled-data generation is strategically interesting.** Several challenges reward *measured* precision/false-positive rates (Hostinger) or reproducible evaluation (AfterQuery), and the usual blocker is having no labelled test set. Browser-based synthetic data generation with no GPU is a cheap way to produce one.
- **IronShard's preloaded challenge datasets** could remove the download cost that makes Stoa (10 GB) and S-Pankki unattractive — worth checking which challenges are actually preloaded before ruling those out on data-access grounds.
- **Arduino UNO Q + Modulino sensors + USB camera** is directly relevant to the Aalto challenge (home sensing of mental state). The Modulino Thermo and Knob are limited, but the camera plus UNO Q compute enables real physiological/behavioural sensing. Note Aalto says a laptop and phone suffice — hardware would exceed that bar, not just meet it.
- **CRACI's €1,000 is nominally CI/CD but explicitly usable for "any compute need"** — the largest team-level compute grant in the list. Worth asking at their booth what that actually permits.
