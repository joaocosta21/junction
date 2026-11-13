# Aalto University — "Beyond the Clinic"

Build the product that helps people stay well at home after depression treatment, using anything from natural stimuli to a phone, music, games, light or AI.

## Context
**Transcranial magnetic stimulation (TMS)** is used in hospitals to treat severe depression, requiring multiple brief daily visits. Even when treatment succeeds, **depression can return** — so "maintenance" treatment at home is wanted.

In hospital you have blood samples, fMRI/MEG/EEG scans, and a psychiatrist. At home you have none of these, except occasional remote psychotherapy that is difficult or expensive. But **brain activity and mental condition at home can be measured in several ways.** No good solution yet exists for home maintenance treatment — that's the challenge.

## The ask
Home-based maintenance treatment could be **"closed-loop"**: individualised based on how the patient's brain reacts to interventions. The product can work as a loop:
**sense how someone is doing → respond with something that helps → learn what works best for that person.**

## Who to design for
- **People after TMS treatment** who want to keep feeling well once daily hospital visits end.
- **Anyone at risk of depression**, who could benefit from early everyday support.
- **Clinicians**, who want to follow patients between visits without adding workload.

## No special hardware needed
**A laptop and a phone are enough to build something great.**

## What could help people stay well
- Cleverly designed **sensory stimulation** (auditory, visual, touch, smell, taste) — e.g. music, rhythmic lights or colours
- Social interaction, meditation, yoga, physical exercise
- Regular visits to forests or the sea — **or experiencing them in VR** when going out is hard
- Computer games (e.g. Soihtu)

## How to sense how someone is doing at home
- **Mobile phone**: sounds, voice, movement (acceleration), facial expressions, sleep, daily routines
- **Wearables** (e.g. smart rings): heart signals (**HRV**), sleep, activity, and changes in the **autonomic nervous system — a very important indicator of mental state**
- Many other sensors exist or can be invented

## Product directions they'd love to see
- **Everyday companion** — a phone or AI check-in that notices changes over time and suggests the right thing at the right moment
- **Sensory experience** — music, light or VR adapting to how the person is doing that day
- **Game** — fun to play daily, also supports mood and wellbeing
- **Smart home** — lights and sound gently changing through the day
- **Social** — a way for friends or peers to stay close and reach out when it matters
- **Clinician view** — a simple way for professionals to see who might need a call

For inspiration: Meru Health and other companies working on depression.

## Resources and support
- **Published research and open data** — pointers to studies and openly available datasets to build on
- **Expert mentors** — researchers from Prof. Risto Ilmoniemi and Prof. Pantelis Lioumis' group (Department of Neuroscience and Biomedical Engineering), plus Aalto Innovation support
- Main contact: **Myungji ("MJ") Suh**

**Demos subject to confirmation with the lab:**
- A **live brain stimulation demo** — TMS in action, seeing a magnetic pulse activate the brain
- **Brainwaves in real time** — portable EEG demo at the booth

## Implications for how we build
- **No judging rubric was published in this brief** — unlike AstraZeneca, AfterQuery or Cala. Worth asking at the booth what they actually weight; absent that, Junction's own criteria (innovation, impact, implementation) are the fallback.
- **The closed-loop framing is the distinguishing idea.** Sense → intervene → learn-per-person. A static meditation app ignores it; the loop is what they described twice.
- **Phone-only sensing is explicitly sufficient**, which keeps scope realistic: accelerometer, microphone, screen/routine patterns, optionally camera. HRV needs a wearable we may not have.
- **The "learn what works for this person" part is where most teams will hand-wave.** With a weekend and no real patients, we can't train a personalisation model on real response data — so decide early whether to demonstrate it on synthetic/simulated response data and *say so honestly*, or scope it as an explicit design.
- **Clinical sensitivity:** this is a vulnerable population and a medical context. Any demo should avoid implying diagnostic capability, and should have a clear escalation path (what happens when signals look bad). Judges from a neuroscience lab will notice if that's missing.
- No patient data is offered — only published research and open datasets.
