# CyberCore: real-parts build plan (2026-11-16)

The rev 0.2 board in `pcb/` is a concept: our own GPU and the AMD socket can't be built or sourced.
This plan builds a CyberCore that can actually be bought, installed and run, from parts that exist today.

**In one line:** an 8-GPU AMD Instinct server (one OEM box, ready-made), set up and branded as CyberCore,
installed at home on its own 3-phase power, or in a data centre.

## 1. The machine

Every option is one 8U rack server from an AMD partner (Supermicro, Gigabyte, Dell, HPE, Lenovo, Cisco):
2 AMD EPYC CPUs + 8 Instinct GPUs on AMD's own baseboard, with all GPU memory linked by Infinity Fabric.

| Option | GPU memory | GPU bandwidth | GPU power | Cooling | Price signal |
|---|---|---|---|---|---|
| **A. 8 x MI350X (recommended for home)** | 8 x 288 GB = **2.3 TB** HBM3E | 8 x 8 TB/s = 64 TB/s | 8 x 1.0 kW | Air | Ask for a quote. Same class as B |
| B. 8 x MI355X | 2.3 TB HBM3E | 64 TB/s | 8 x 1.4 kW | Direct liquid only | One listed new server: $726,418 (Gigabyte G893-ZX1-AAX4) |
| C. 8 x MI300X (budget) | 8 x 192 GB = 1.5 TB HBM3 | 8 x 5.3 TB/s = 42 TB/s | 8 x 0.75 kW | Air | New: ~€278-309k ex VAT; refurbished listed, no price shown |
| D. 8 x MI440X (wait) | Not final. If 432 GB each: ~3.5 TB HBM4 | Not final | Not final | "Fits existing power and cooling" | Announced for 2H 2026, no price yet |

Why A over B: same memory size and bandwidth, and bandwidth is what sets tokens/s.
MI355X is only ~10% faster in compute, but it needs a coolant distribution unit and a water loop to outside.
Air cooling is the easier home project.

Why D matters: it is the only single box that could hold a 5T model at 4-bit (2.5 TB + cache).
Ask the OEM for MI440X memory size and ship date before buying A or B.

Typical extras in the quote:
- 2 x EPYC 9005, 1.5-3 TB DDR5
- 4-8 x NVMe Gen5 (30 TB+ for the model store)
- 1-2 x 400G NIC (needed only if a second CyberCore is ever added)
- BMC with Redfish

## 2. What it runs, and how fast

The largest open-weight model right now is Kimi K3, about 2.8T total parameters with ~104B active per token.
This needs checking against the official model card. No 5T open model exists yet.

| Model | Size at 4-bit (FP4) | Fits in 2.3 TB (A/B)? | Fits in 1.5 TB (C)? |
|---|---|---|---|
| Kimi K3 (~2.8T, ~104B active) | ~1.4 TB | Yes, with ~0.9 TB left for context cache | Barely, with little cache |
| DeepSeek V4-Pro (1.6T, 49B active) | ~0.8 TB | Yes, easily (could even run at 8-bit) | Yes |
| Future 5T MoE (~150B active) | ~2.5 TB | No. Needs 3-bit, two servers, or option D | No |

Speed for Kimi K3 at 4-bit on A or B:
- Each token reads ~52 GB of active weights. Over 64 TB/s, that is a theoretical ceiling of ~1,200 tok/s.
- In practice, the GPUs spend time talking to each other, and one user's stream is far below that ceiling.
- **Estimate:** roughly 50-150 tok/s for one user, and thousands of tok/s in total with many users at once.
- **Measure before buying** (step 1 below).

For comparison, the rev 0.2 concept board was ~25-30 tok/s, because its memory ran at 3.7 TB/s, not 64.

## 3. Power, cooling, noise (the hard part at home)

**Power**
- Option A peaks around 10-12 kW, and B around 13-14 kW. Measure under load. One reviewer estimates 14-18 kW for these systems.
- The air-cooled Supermicro MI350X server has 6 x 5,250 W supplies (3 + 3 redundant).
- That needs dedicated 3-phase circuits from the fuse box: an electrician job.
  - Check the house main fuse first. A 10-14 kW server can use most of a normal house's capacity.
- Electricity estimate (assumes 1.5 NOK/kWh with grid fees; check your own price):
  - Full load: ~11 kW x 730 h = ~8,000 kWh, so ~12,000 NOK a month.
  - Idle: ~1.5-2 kW, so ~1,600-2,200 NOK a month.

**Heat**
- All of that power turns into heat: 10+ kW is several large space heaters.
- In winter, ducting the exhaust into the house is free heating. In summer it has to go outside.
- Option B (liquid) adds:
  - an in-rack coolant distribution unit (CDU)
  - a dry cooler outdoors, or a heat exchanger into the hot-water tank

**Noise**
- Air-cooled 8-GPU servers are about as loud as a leaf blower under load. It needs its own room, garage or insulated closet.

**Space**
- 8U, roughly 100-150 kg.
- Needs a 42U rack with rails, about 1.2 m deep, on a floor that can take the weight.

**The easy alternative:** colocation in a data centre. Power, cooling and noise are then someone else's job.
- Pick a region with cheap, renewable data-centre power.
- Reach it from home over a VPN or tunnel.

## 4. Software

- Ubuntu Server LTS + ROCm (AMD's GPU stack)
- AMD's ROCm container images for **vLLM** or **SGLang**, serving an OpenAI-compatible API with all 8 GPUs (tensor / expert parallel)
- Models live on the local NVMe, copied from a local archive or downloaded from Hugging Face
- Exposed as a CyberCore API through a tunnel, behind an access gate (owner only at first)
- BMC Redfish data (power, temperatures, fans) goes to a telemetry dashboard and the CyberCore status panel

## 5. What is "ours" about it

You can't build the GPUs and board yourselves, so the CyberCore part is the setup around them:
- **Name and look:** a custom front bezel (CNC aluminium or 3D print) with the CyberCore wordmark.
- **Status panel:** a small KiCad board we design and order for real. It would use an ESP32-S3 and an LED matrix or e-ink display, all parts with public pinouts. It reads the BMC over Redfish and shows tok/s, power and temperatures.
- **CyberCore software:** the serving stack, model manager, API keys and dashboard.

## 6. Steps

1. **Rent before buying.** Rent one 8 x MI355X node for a day. Listed prices are about $25-65 an hour for 8 GPUs, so a day costs roughly $600-1,600.
   - Run Kimi K3 at 4-bit in vLLM and SGLang, and write down the tok/s for 1, 8 and 64 users.
   - Use this to pick an option on real numbers.
2. **Decide home or colocation.**
   - For home: get an electrician to check the main fuse and quote dedicated 3-phase circuits.
   - Pick the room, the rack and the airflow path.
3. **Get OEM quotes** for options A and D (plus B if going liquid).
   - Ask about MI440X memory size, ship date and lead time.
   - Most capacity is sold on contract, so listed prices are only a signal.
4. **Install and burn in.** Run 48 h at full load while logging power and temperatures.
5. **Software** (section 4), then branding (section 5).

Break-even against renting: $726k / ~$40 an hour = ~18,000 hours, which is about 2 years running 24/7.
Buying wins only if it really runs most of the time.

## Sources (checked 2026-11-16, prices are single data points)
- MI355X server listing and price: https://servermall.com/en-us/sets/servers-with-amd-mi355x/
- MI355X rental price comparison: https://savrn.com/ai-index/pricing/gpus/mi355x
- MI355X 1.4 kW, liquid cooled: https://www.theregister.com/2025/06/12/amd_mi355x/
- MI350X vs MI355X power and cooling: https://www.tomshardware.com/pc-components/gpus/amd-announces-mi350x-and-mi355x-ai-gpus-claims-up-to-4x-generational-gain-up-to-35x-faster-inference-performance
- Supermicro MI350X server review (power supplies): https://www.storagereview.com/review/supermicro-jumpstart-review-h14-with-amd-instinct-mi350x
- MI300X server prices: https://servermall.com/en-us/sets/servers-with-amd-mi300x/
- MI400 family incl. MI440X 8-GPU: https://www.tomshardware.com/tech-industry/artificial-intelligence/amd-touts-instinct-mi430x-mi440x-and-mi455x-ai-accelerators-and-helios-rack-scale-ai-architecture-at-ces-full-mi400-series-family-fulfills-a-broad-range-of-infrastructure-and-customer-requirements
- MI455X 432 GB HBM4 timing: https://www.insidedeeptech.com/amd-helios-mi455x-rack-full-guide/
- Largest open-weight models (Kimi K3 etc.): https://tech-insider.org/best-open-source-llm-2026/
