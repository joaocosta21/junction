# Bahn Express — "Spread"

Run a car transport company for a week.

## The world
Bahn moves cars for car dealers; a freelance driver drives each car on its own wheels. **Spread** is that work as a simulated world: a whole week in Finland, with its dealers, cars, deadlines and drivers.

Your team builds the system that runs the company for that week:
- A dealer asks you for a price — **and asks a competitor too**. Quote too high and you lose the car.
- Win it, and you post the drive as a gig in the drivers' app and **choose the fee**.
- Pay too little and no driver takes it in time, and the car arrives late.

## Scoring
- **Score = gross margin** = what dealers pay you − what you pay drivers.
- **At least 90% of cars must arrive by their deadline.**
- Most money takes you to the top of a shared leaderboard.

## Start
- Create your team at **https://spread.bahnexpress.com/join**, event code **`spread-kmu9z6`**.
- Site has everything: handbook, rules, API reference, TypeScript and Python kits, leaderboard.
- Give your agent **https://spread.bahnexpress.com/llms.txt**.

## Timeline
- **Ranking rounds open Friday 19:30.** Every team plays the same secret weeks, so the leaderboard shows where you stand. Bahn's own best system plays every round — beat it.
- **Final: Sunday 08:00.** Every team plays its own copy of one secret week, running by itself for ~34 minutes. **Registration closes 07:30.**
- The **10 ranked teams with the highest margin** present to the jury, in 5–10 slides or a short video. The jury judges how **elegant, clear, creative and robust** the system is. Reaching the top 10 is enough — after that, margin no longer counts.

Mentors at the Bahn booth: rules, the world, real dispatch, or ask for a hint.

## Implications for how we build
- **Two-stage game.** Margin only gets you into the top 10; the prize is then decided on elegance/clarity/creativity/robustness of the system. So: optimize margin hard enough to qualify, then spend remaining time making the design defensible and well-presented.
- **Ranking rounds are free feedback from Friday 19:30** against the same secret weeks as everyone else, including Bahn's reference system. Iterating against the leaderboard is the core development loop — get a working agent submitting early, however naive.
- Two coupled pricing decisions: **quote to the dealer** (win-rate vs. revenue) and **fee to the driver** (acceptance/on-time vs. cost). The 90% on-time constraint is a hard floor — a cheap fee that misses it invalidates the run.
- The **Sunday 08:00 final with 07:30 registration cutoff** is before the Junction 10:00 submission deadline. Both land in the same morning — plan the night before accordingly.
