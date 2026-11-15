# Atech — "Atech Real World Challenge" (tech track)

The API for the physical world.

## The ask
**Build a physical device that solves a real problem for a real person**, using Atech modules as its body and AI as its brain. Pick someone — a farmer, a nurse, a cyclist, your grandmother, your flatmate — and give them a device that **senses, reacts or connects in a way software alone can't**.

**Using Atech hardware is required**; how you combine it with other tools, APIs and models is up to you.

## Minimum requirements
- **Atech modules used in the demo** alongside a real-world solution
- **Share a link to a summary / post about it in their Discord**

## Submission requirements
- **Live demo on the hardware**
- Public GitHub repo or exported Atech project
- ~2-minute video / live demo

## The technology
A kit of **snap-together ESP32-based modules** (sensors, motion, connectivity) plus an AI platform that **writes the firmware for you**. Describe the device in plain language; Atech plans it, generates the code, builds it and flashes it to the hardware from the browser. **No breadboards, no soldering, no driver hunting.**

**Modules:** distance, IMU, temperature & humidity, air quality, microphone, speakers, motors, and more.

**Capabilities:**
- Build at atech.dev, flash from the browser over USB
- **Python library: `pip install atech`** — use any coding agent
- **Emulator** to test before touching hardware
- **Wi-Fi or Bluetooth** connectivity, to create an API to your AI set-ups

## Quickstart
1. **Pick up your team's kit at the Atech booth** — first come, first served from opening
2. Create an account at https://atech.dev, **redeem code `JUNCTION`**
3. Snap a module onto the base board, plug into laptop with USB-C
4. Open the platform in **Chrome or Edge**, describe a device, e.g. *"Light the LED red when something is closer than 20 cm"*
5. Click flash — device reacts in under a minute
6. Recommended: `pip install atech`, then use a coding agent

**Hardware allocation:** 2–4 boards + modules per team, depending on demand. **Teams return everything after final demos** (winners keep prizes).

## Tips and pitfalls (from their brief)
- **Chrome or Edge only** — Safari and Firefox don't support browser flashing (WebSerial)
- **Use a data USB cable, not charge-only** — spares at the booth
- Start with one module working, then add the next; describe changes step by step
- **On Linux, add your user to the `dialout` group** if the board doesn't show up
- Firmware generation needs internet; **flashed devices run standalone**

## Inspiration
- **Assistive devices:** fall detection, posture coaching, smart reminders for people living alone
- **Sustainability:** sensing energy, water, air quality or food waste and acting on it
- **Physical AI:** put an LLM or vision model in a loop with real sensors and actuators
- **Robotics:** give a robot arm or rover new senses with distance, IMU or climate modules
- Tools for makers, labs and classrooms

## Prizes and judging
Winning team gets a **Pro Atech kit** to keep. Runner-ups get Atech kits and swag. Top teams invited to show their project on Atech's channels and **visit them in Copenhagen**.

## Support
- **#atech on Junction Discord** + the Atech booth
- **Mentors throughout the event, including a night shift**
- Software escalation: julius@atech.dev · Hardware escalation: tomas@atech.dev
- Main contact: **Gustav Hugod**, CCO — gustav@atech.dev
- Technical contact: **Tomas Harmer**, CTO — tomas@atech.dev
- Docs: https://atech.dev/docs · Starter repo: https://github.com/atechdotdev

Copenhagen-based; 250+ customers including Stanford and UC Berkeley labs. They're hiring.

## Implications for how we build
- **Ninth stackable award, but the only one requiring physical hardware checkout.** Kits are first come, first served with only 2–4 per team — **if this is a contender, go to the booth immediately.** This is the one award that can become unavailable.
- **Hardware forces a live physical demo**, which is higher-risk than a web demo but far more memorable in peer review — a working device on the table is unusually persuasive when 2,000 people are pitching software.
- **Strong fit with the Aalto challenge** (see [AALTO-CHALLENGE.md](AALTO-CHALLENGE.md)): Aalto wants home-based sensing of mental state, and Atech provides IMU (movement), microphone (voice), and air quality/climate modules. Aalto says "no special hardware needed, a laptop and phone are enough" — but a real sensing device would exceed that bar rather than meet it.
- Also fits assistive/fall-detection ideas directly, which is their own first inspiration bullet.
- **Everything is returned after demos**, so don't plan a project that depends on keeping the hardware.
