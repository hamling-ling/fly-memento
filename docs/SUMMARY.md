# 研究ログ

これは 2026-11-18 から 11-20 の研究メモの写しである。ロボットの実装はリポジトリ直下の `brain/` `sim/` `robot/` に移した。設計の現在地は [DESIGN.md](DESIGN.md)。ログ本文は当時のパス（`/workspace/mb-oscillation` や `robot_sim/`）のまま残してある。MP1–MV1 のギャップ結合が作業仮説であることは、ログの中の NOTE（2026-11-19）と、末尾のロボット段階に書いてある。

---

# Mushroom body KC–APL limit-cycle: first rough pass (2026-11-18 JST)

Data: FlyEM/Janelia MaleCNS **v1.0** flat-connectome (public GCS, no token needed):
gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/ — body-annotations (minconf 0.5), body-neurotransmitters, connectome-weights (minconf 0.5).

Subnetwork: KC 4064 (KCg-m 1342, KCab-s 657, KCab-m 536, KCab-c 488, KCa'b'-ap2 291, KCg-d 206, KCa'b'-m 205, KCa'b'-ap1 199, KCab-p 129, other 11), APL 2, DPM 2, MBON 97 (ACh 50/Glu 26/GABA 21), PAM 316, PPL1 16, uniglomerular ACh PN 294 (ALPN, excl. M_/MZ_ and GABAergic).
Synapse totals (pre→post): KC→APL 210,352; APL→KC 196,200; KC→KC 1,153,845 (53% of KC input); uPN→KC 388,237; KC→MBON 463,640; MBON→PAM 6,585; MBON→PPL1 4,435; PAM→KC 173,789; PPL1→KC 49,256; PAM→MBON 28,546; PPL1→MBON 11,070; KC→DPM 95,527; DPM→KC 32,795. See stats.txt.
Weights = sign(consensus NT) × synapses / total input synapses of postsynaptic cell; g = global gain.

Results: see hopf_grid.csv, indiv_eigs.csv, fp_lin_*.csv, fig1–3.

## Key findings
1. Pooled KC<->APL loop, no KC-KC, first order, no delay: no Hopf at any g (as theory says). Hopf appears once APL output is delayed or filtered. Open-loop gain at Hopf G = g^2·0.866·0.090: about 3.9 at d=5 ms (τAPL=5) giving ~36 Hz; about 1.7 at d=20 ms (τAPL=2) giving ~17 Hz. A slower APL raises the needed gain and lowers the frequency. Onset is 9–130 Hz over the grid, mostly 15–60 Hz at d 2–20 ms.
2. With KC-KC counted as excitatory, the pooled 2-node model reaches Hopf at g≈2 with no delay when τAPL≫τKC (Wilson–Cowan route, 2–5 Hz). In the 11-type and individual models, a non-oscillatory real-eigenvalue instability comes first (W eigenvalue 0.567 real, so g≈1.76). The block-shuffled W instead has its rightmost eigenvalue complex (0.26±0.08i), so the real KC-KC structure favors runaway or bistability over oscillation.
3. Individual model (4064 KC + 2 APL, tanh KC, linear APL, odor-like PN input, no KC-KC, τAPL=2 ms, d=10 ms): the real wiring crosses Hopf at g≈25–30 (~28 Hz), and the deterministic simulation shows a sustained ~29 Hz limit cycle at g=40. Block and within-KC-type shuffles stay stable up to g=80. The real wiring has reciprocity (KC→APL vs APL→KC, Spearman 0.38; shuffled −0.16). With Poisson input, all three wirings show a similar noise-driven ~20–27 Hz resonance peak.
4. Rectification self-limits the loop: raising g silences KCs, which caps the effective gain. In the deterministic simulation, theta=1.5 and tonic settings gave no oscillation.

## LIF version (2026-11-18 JST): lif.py, lif_sweep.py, lif_metrics.py, lif_plots.py
Model: 4064 LIF KCs (tau_m 5 ms, threshold 1, reset 0, refractory 2 ms, synaptic trace 5 ms). APL is graded by default: a leaky integrator with rectified output, then a 10-stage delay chain of total length d. Same MaleCNS v1.0 normalized weights and the same odor pattern (20% of uPNs at 40 Hz, the rest at 2 Hz) as the rate model. Drive amplitude A=10; KC-KC is off unless stated. T=2.5 s, analysis from 0.5 s. Results are in lif_main.csv, lif_extra.csv and lif_noise.csv.
- Deterministic (constant PN) input, τAPL=2 ms, d=10 ms: the real wiring shows a sustained limit cycle for g≥20. APL SD/mean is 0.36–0.61, against ≤0.015 for both shuffles. The late ACF (max over lags 200–400 ms) is 0.67–0.97 against ~0.2–0.35 for the shuffles. Frequency is 33→28 Hz as g goes 20→80. The rhythm shows as synchronized KC volleys in the raster, and a different initial condition reproduces it (seed 1: same f0 and amplitude). With A=5 it also appears from g=20, at 34–29 Hz. Between g=10 and g=20 the amplitude jumps by about 50×; the rate model put its Hopf at g≈25–30.
- Other delay/τAPL settings (5/5, 5/2, 20/5, 5/0) give only small fluctuations, APL SD/mean ≤0.04. The largest is 5/5 at g=80 (~53 Hz, ACF 0.88), possibly near onset. So a long delay relative to τAPL is still the key ingredient.
- KC sparseness at the oscillating point (deterministic input, real wiring): time-averaged fraction of KCs active per 50 ms bin is 0.13 (g=20), 0.10 (g=40), 0.044 (g=80); mean KC rate 11.6, 5.5, 2.1 Hz. Under Poisson input the per-50 ms fraction is 0.29–0.10, and 53–79% of KCs fire at least once in 2 s.
- Poisson PN input (3 seeds): the cycle is mostly smeared into noise resonance. All three wirings show a broad ~20–30 Hz peak. In the noise sweep at k=1 (Poisson-level noise), the real wiring has a slightly higher late ACF (0.18–0.28 against 0.12–0.14) and a stable f0 (27–28 Hz, SD ≤2 Hz across seeds). The main sweep, run with different random draws, shows no difference (~0.2 for all), so the evidence at k=1 is weak.
- Reducing PN noise (k-fold more events of 1/k size; same mean, variance/k): the real wiring's late ACF rises to 0.77–0.97 at k≥100, with zero f0 spread across seeds. The shuffles stay at 0.14–0.25. The real wiring has a genuine limit cycle that strong Poisson PN noise largely masks.
- Spiking APL (LIF, tau_m 10 ms, 2 cells): APL's own regular spiking produces a 90–150 Hz component in all wirings. Only the real wiring at g≥20 shows a 24–31 Hz rhythm (deterministic input, ACF 0.66–0.99). Under Poisson input the real wiring's late ACF is 0.27–0.43 at g≥20, against 0.14–0.26 for the shuffles.
- KC-KC included (as excitatory): strong population bursting at 17–21 Hz in the real wiring for g≥10 (deterministic) and g≥20 (Poisson), with 60–94% of KCs active. This is a relaxation oscillation, KC-KC runaway cut off by APL, and is not sparse coding. The shuffles show it at some g too.
- Figures: figL1_lif_traces.png (raster, APL trace, PSD and ACF; real against both shuffles; deterministic and Poisson; g=40, τAPL=2, d=10) and figL2_lif_summary.png (amplitude against g, persistence against PN noise, delay dependence).
- Caveats: the late-ACF metric has a noise floor of ~0.2. The cv_period peak detector is unreliable because the trace has a harmonic. Only one odor and one seed per shuffle type; no synaptic conductances; same point-APL simplification as before.

## Hysteresis / bistability with KC-KC on (2026-11-18 JST)
Scripts: hyst.py, hyst_sweep2.py, hyst_ic3.py, hyst_plot_rate.py (rate model); lif_hyst.py, lif_dwell.py, lif_hyst_plot.py (LIF).
Results: hyst_sweep2_rate.csv, hyst_ic3_rate.csv, hyst_ic_long.csv, lif_hyst_sweep_A3.csv, lif_hyst_sweep_A10.csv, lif_dwell.csv.
Figures: figH1_rate_hysteresis.png, figH2_lif_hysteresis.png.

Rate model: per-neuron, KC = tanh(relu(x - θ)), APL graded with τ 5 ms and no delay, same odor input, drive amp 3. Each step is 300 ms with the state carried over.
- θ=0.3 (KCs already mostly active, 59% at g=1): no clean bistability. There is only a small loop (Δ≤0.04) at g≈3.7–4 with poor convergence. The linear "real instability" at g≈1.76 does not appear as a jump; activity just rises smoothly.
- θ=1.0 (sparse low state, ~11% of KCs active), real wiring: clear hysteresis.
  - Up sweep: stays sparse (mean 0.038, 11% active, 0.1% saturated) until a partial jump at g=6.75 (17% active) and a full jump at g=8.25 (27% active, 24% saturated, mean 0.25).
  - Down sweep: stays high until g=4.5, back to sparse at 4.25.
  - Loop g≈4.5–8.25, largest branch gap 0.205.
  - Two-initial-state check, 2 s runs with no change over the last 500 ms: g=5 has a low state (mean 0.038, 11% active) and a high state (0.10, 17% active, 4.9% saturated); g=6 has 0.038 vs 0.228 (27% active, 19% saturated). Two stable fixed points.
- PN drive sweep at g=6 (real wiring): loop from amp 0.5 to ~5.5. On the down branch, activity survives at amp 0.5 (3.3% of KCs active) while the up branch is silent, i.e. self-sustained activity. At g=5 the loop is amp 2.0–5.0.
- Controls:
  - Block shuffle: no loop at θ=1 with APL×1, for both g and drive sweeps.
  - Within-type shuffle: narrower loop, g 5.5–6.75, gap 0.18.
  - KC-KC off: no loop.
  - The high state in the real and type-shuffled wiring is carried by local KC-KC clusters. Starting just the top 200 KCs of the leading KC-KC eigenvector gives the high state for real g 4.75–8. Block never holds a cluster state with APL≥0.5.
- APL strength (APL→KC scale), real wiring loop: ×0 g 3.75–8.25 (gap 0.89, global runaway to saturation); ×0.5 g 4.25–6.75 (gap 0.35); ×1 g 4.5–8.25 (gap 0.21); ×2 g 5.0–9.75 but the gap is only 0.056 (a small cluster state). Stronger APL shrinks the high state's size and pushes the loop to higher g, but does not remove it. Block shows a loop only with APL×0 (g 4.5–6.25) or ×0.25.

LIF: 4064 LIF KCs with KC-KC on, graded APL with τ 5 ms and no delay. Drive A=3, because at A=10 KCs fire at 100–240 Hz for every g and there is no sparse state. Each step is 400 ms with the state carried over.
- Constant input:
  - Real wiring: up ignition at g 1.5–2.0, down-branch return at 1.5→1.0. Narrow loop ≈ g 1.5–2.
  - Two-state check (4 s): g=1.75 gives 20 Hz (20% of KCs spiked) vs 86–88 Hz (46%); g=2.0 gives 60 vs 101 Hz.
  - Within-type shuffle: g=1.75 gives 25 vs 86 Hz.
  - Block shuffle: the sweep shows a loop at g 2.5–3.0, but the two-state check at g 2.5–3.0 converged to one state (27–31 Hz) from both starts. Not confirmed.
  - KC-KC off: no loop (rate falls monotonically, 12→3 Hz).
  - There is also a second small loop between two high, non-sparse states (110–167 Hz) at g 8–12.
- Poisson PN input: at g 1.5–1.75 both starts converge to the same noisy ~35–40 Hz state (91–92% of KCs spiked in 4 s), so the noise erases the bistability. At g=2 both starts sit at ~83 Hz (real). One noise-induced escape low→high was seen (type shuffle, g=2, at ~2 s). No back-and-forth switching was seen in 4 s, so dwell times cannot be estimated (they are ≫4 s or the window is too narrow). The threshold crossings counted in the block runs are fluctuations around a single ~40–50 Hz mean, not state switches.
- The LIF high state (~85–100 Hz mean, ~45% of KCs spiking) is far from physiological KC activity.

Caveats: KC-KC synapses are mostly axo-axonal in the lobes/calyx and are treated here as excitatory drive onto the KC body. The low/high states depend on θ, the KC saturation (tanh) and the drive level: with θ=0.3 there is no clean loop, and with A=10 in LIF no sparse state. g has no physical calibration. One odor pattern and one shuffle seed per type; LIF switching runs are 4 s and single-seed.

## Literature (2026-11-18 JST; only sources found and read in search results/pages this session)
KC–KC axo-axonal synapses
- Takemura et al. 2017 eLife, α-lobe connectome (https://pmc.ncbi.nlm.nih.gov/articles/PMC5550281/): extensive KC–KC synapses in α-lobe compartments, mostly in "rosettes", often with both KCs also synapsing onto the same MBON.
- Manoim et al. 2022 Curr Biol (https://www.cell.com/current-biology/fulltext/S0960-9822(22)01451-8): KC axo-axonic connections are mediated by muscarinic mAChR-B. They suppress odor-evoked Ca2+ and dopamine-evoked cAMP in neighbouring KCs; knockdown in γ KCs gives unspecific learning; there was no effect in the calyx. The paper notes that KC axons appear to lack nicotinic responses (local ACh/nicotine gave no Ca2+ signal).
- Bielopolski et al. 2019 eLife (https://pmc.ncbi.nlm.nih.gov/articles/PMC6641838/): mAChR-A (Gq-type) is on KC dendrites and inhibits odor responses; needed in γ KCs for aversive learning. Muscarine reduced KC responses.
- 2026 Curr Biol, "A voltage-dependent switch underlies efficient yet specific learning and memory" (https://www.cell.com/current-biology/fulltext/S0960-9822(26)00014-X): per the abstract/search summary, mAChR-B is voltage dependent, inhibiting plasticity in weakly active KCs while permitting it in strongly active ones. The full text was blocked (403), so details are unread.
- KC gap junctions: Liu et al. 2016 eLife (https://pmc.ncbi.nlm.nih.gov/articles/PMC4909397/) reported KC–KC dye coupling in calyx and lobes (INX5/INX6 needed for visual memory). PLoS Genet 2019 "Electrical synapses between mushroom body neurons are critical for consolidated memory retrieval in Drosophila" (https://pmc.ncbi.nlm.nih.gov/articles/PMC6529013/): INX5-dependent αβ KC electrical synapses are needed for consolidated memory retrieval. Gap-junction strengths are not in the connectome.
APL
- Amin et al. 2020 eLife (https://pmc.ncbi.nlm.nih.gov/articles/PMC7541083/): APL is non-spiking. Its activity and its inhibition of KC dendrites and axons are spatially localized (inhibition somewhat less so than activity), so APL can differentially inhibit compartments. A hemibrain model predicts KC self-inhibition via APL exceeds inhibition of other KCs.
- Prisco et al. 2021 eLife (https://pmc.ncbi.nlm.nih.gov/articles/PMC8741211/): in the calyx, APL makes inhibitory and reciprocal synapses on PN boutons and KC dendrites, normalizes microglomerular responses, and is regionalized around PN input.
- Inada, Tsuchimoto & Kazama 2017 Neuron (https://www.cell.com/neuron/fulltext/S0896-6273(17)30563-9): APL responds locally within a lobe or globally depending on stimulus strength; α′/β′ KCs recruit APL inhibition most effectively.
- Lin et al. 2014 Nat Neurosci (https://www.nature.com/articles/nn.3660): KC–APL negative feedback maintains sparse, decorrelated coding.
- Liu & Davis 2009 Nat Neurosci (https://pmc.ncbi.nlm.nih.gov/articles/PMC2680707/): APL is GABAergic and suppresses learning. RDL (GABA-A) on MB neurons: J Neurosci 2009 (https://www.jneurosci.org/content/29/5/1573), Neuron 2007 (https://www.cell.com/neuron/fulltext/S0896-6273(07)00832-X).
- Wu et al. 2011 Curr Biol (https://www.cell.com/current-biology/fulltext/S0960-9822(11)00232-6): APL (INX7) and DPM (INX6) form heterotypic gap junctions, mainly in α′β′ lobes.
- APL time constants and the APL→KC synaptic delay were not found as numbers in these sources (unknown).
Models
- Rapp & Nawrot 2020 PNAS (https://pmc.ncbi.nlm.nih.gov/articles/PMC7668073/): spiking MB model with a global APL; KCs under 2% active.
- Kennedy 2019 bioRxiv (https://doi.org/10.1101/783191): dynamic olfactory-system model.
- Amin et al. 2020 (above): connectome model with distance-dependent APL inhibition.
Oscillations / persistence
- Tanaka, Ito & Stopfer 2009 J Neurosci (https://www.jneurosci.org/content/29/26/8595): odor-evoked ~10 Hz LFP oscillations in the fly MB calyx, generated in the antennal lobe (LN2 GABAergic LNs) and carried by PNs. Picrotoxin abolishes them.
- Turner et al. 2008 J Neurophysiol (https://journals.physiology.org/doi/full/10.1152/jn.01283.2007): per the search summary, single-KC recordings showed no consistent periodicity. The ~20 Hz LFP–KC phase locking is a locust result (Laurent & Naraghi 1994, https://www.jneurosci.org/content/14/5/2993).
- I found no report of persistent/bistable KC activity in Drosophila in these searches.
Evidence status for model choices
- Supported: KC–KC acts axo-axonally via inhibitory mAChR-B (not soma excitation); KC–KC is mostly in lobes (MaleCNS v1.0: 3% of KC→KC synapses in the calyx); APL is non-spiking with localized activity and inhibition of dendrites and axons; APL is GABA/RDL.
- Unknown: APL τ, delay, the inter-compartment coupling strength, the mAChR-B time constant, and gap-junction weights.

## Revised model (compmb.py / compsim.py; per-ROI synapses from syn-partners primary_post, MaleCNS v1.0)
- ROIs used: CA, PED, aL, a′L, bL, b′L, gL per side, plus "other". KC→KC is 3.0% calyx and the rest lobes/PED/other; APL→KC is 15.6% calyx.
- KC spiking (LIF) is driven by uPN input minus APL inhibition in the calyx only (eps=0). This follows Prisco 2021, Amin 2020, and Manoim 2022's "no calyx effect".
- Lobe APL inhibition and KC–KC (mAChR-B-like, slow trace τ_m=200 ms, assumed) act as presynaptic gating of each KC's local output per ROI. Both signs were tested (inhibitory = evidence; facilitatory = control).
- APL: one graded compartment per (APL cell, ROI), driven by the gated KC output in that ROI, with coupling κ between compartments of the same cell (κ=0, 0.1 local; κ=10 strongly coupled). "Old-like" = κ=10 plus lobe inhibition on the soma (eps=1).
- Results (rev_sweep.csv, 1134 LIF runs; rev_hyst.csv):
  - Local APL (κ 0–0.1), constant input: no limit cycle at any g (10–320) or delay setting (2/10, 5/5, 5/0 ms) in any wiring; APL SD/mean ≤0.021. The earlier ~28 Hz cycle disappears.
  - κ=10: real wiring oscillates at g=80–160 (SD/mean 0.22–0.35, ACF 0.99, 26–27 Hz). Type shuffle is weaker (0.08–0.10 at g 160–320); block shows none (≤0.005).
  - Old-like: oscillates in all wirings from g≈20–40 (20–25 Hz), so the wiring specificity is weaker than in the earlier point-APL model.
  - Poisson input: all models show a broad noise-driven 20–30 Hz peak.
  - KC–KC gating (either sign) changes neither the oscillation nor the KC spiking.
  - Hysteresis: none. Up/down branches differ by ≤4% relative for real/type/block, KC-KC inhibitory/facilitatory, constant/Poisson, A=3 and 10. The old excitatory-KC-KC bistability does not survive.
  - Sparseness (local, constant input, A=10): fraction of KCs active per 50 ms is 0.15 (g=40), 0.07 (g=80), 0.03 (g=160), at 25/12/5.5 Hz.
- Figure: figR1_revised_model.png.
- Caveats: ROI-level (lobe) compartments, not MBON/DAN compartments (primary_post is lobe-level). APL compartments are normalized by local input. All time constants are assumptions. The mAChR-B voltage dependence is not modelled. Gap junctions (KC–KC, APL–DPM) are absent. One odor; one shuffle seed.

## 刺激実験 (2026-11-18): 文献準拠改訂LIFモデルでPN入力だけを変える
Model unchanged (compsim.py; per-ROI APL compartments, calyx-only soma inhibition, KC-KC = inhibitory mAChR-B-like axonal gate gkk=2, τ_APL 2 ms, delay 10 ms, A=10).
Models: local0 (κ=0), local0.1 (κ=0.1) = test models; coupled10 (κ=10) and oldlike (κ=10, eps=1, gkk=0) = references.
Wirings: real / within-type shuffle / block shuffle. g = 40, 80, 160. Normalisation fixed to the baseline odour (20 % of uPNs at 40 Hz).
Scripts: stim_sweep.py (runs, stim/*.pkl, 1704 runs), stim_an.py, stim_ring3.py (damped-sinusoid fit), stim_plot1.py, stim_plot2.py.
Tables: stim_breadth.csv, stim_volley.csv, stim_volley_ringfit.csv, stim_force.csv, stim_force_resonance.csv, stim_force_tables.txt, stim_breadth_tables.txt.
Figures: figS1_stim_volley_forcing.png, figS2_stim_breadth.png.

**Exp 1, breadth/rate (constant drive; frac_on 0.1–1.0 × rate 40/100 Hz = 0.5–12.5× baseline):**
- The local models never oscillate in a sustained way. APL SD/mean is ≤0.01 in almost all conditions; the maximum is 0.044 (local0.1/real, g=80, 10 %·40 Hz).
- Stronger drive makes things *more* stable. In coupled10/real, the oscillation present at baseline (SD/mean 0.2–0.45) disappears at high drive: at g=80 for 20 %·100 Hz and above; at g=160 for 100 %·100 Hz.
- Globalness does not increase with breadth. With Poisson input at g=80, the mean pairwise correlation across APL ROI compartments is about 0.36–0.47 for local0 and about 0.48–0.60 for local0.1, roughly flat with breadth. Real wiring is slightly *less* correlated than the shuffles. coupled10 sits at about 0.8–0.9 and oldlike at about 0.9–0.97.
- So the Inada-2017 local-to-global switch is not reproduced through PN breadth alone in this model.
- KC sparseness tracks drive. At g=80, the fraction of KCs active per 50 ms rises from 0.05 to 0.30 (local).

**Exp 2, synchronous volley** (3 spikes per active PN, at 800, 1400 and 2000 ms; Gaussian jitter SD 0/2/5/10 ms; deterministic background):
- All local models show damped ringing at about 30 Hz (29–32 Hz). Damped-sinusoid fit R² is 0.90–0.98.
  - τ is 40–68 ms at g=40 and 25–60 ms at g=80–160, giving Q ≈ 2–7.5.
  - Real vs shuffle at g=40: Q is 6.5 (real) vs 4.6 (type) vs 3.9 (block) for local0.1, and 5.6 vs 4.4 vs 3.7 for local0.
  - At g=160 the real wiring is the *most* damped (Q 2.0–2.8 vs 3.5–4.9). Wiring dependence is therefore not monotonic.
- Jitter of 2–5 ms barely changes the ringing. At 10 ms SD the ringing is lost (fit Q < 0.5).
- The response returns to baseline. No volley switches the system into a sustained oscillation.
- coupled10 rings at 26–27 Hz. Its Q grows with g (real: 7.1 at g=40), and it is already oscillating at g≥80.
- oldlike already oscillates before the volley in all conditions.

**Exp 3, periodic forcing** (sin depth 0.5, or 10 ms pulse trains with the same mean; 2–60 Hz; 500–2000 ms; recovery watched until 2500 ms):
- **Resonance.** For sinusoidal forcing in local models, APL gain (relative modulation ÷ input depth) is about 0.9 at 2–13 Hz and peaks at 24–27 Hz with a gain of about 1.9–2.3, i.e. 2.0–2.6× the low-frequency gain.
  - The peak is coarse: the frequency grid is 20/24/27/30, and the half-power bandwidth is 10–19 Hz, so Q_bw ≈ 1.3–2.7.
  - Real wiring has slightly higher peak gain (2.08 vs 1.98 vs 1.89 at g=40) and a broader peak.
  - References peak lower: coupled10 at 24 Hz (gain 1.6–2.2), oldlike at 20 Hz.
- **10 Hz (antennal-lobe frequency, Tanaka 2009).** Gain is about 1: the circuit simply follows the drive, with no amplification. The entrained power fraction is 0.74–0.93, about the same as the shuffles.
- **About 27 Hz.** Gain is highest and entrainment is 0.92–0.96.
- **Subharmonics.** Power at f/2 appears only at 60 Hz, with an f/2 to f ratio of about 1.1–1.3 in local real and type. This is consistent with 2:1 locking onto the ~30 Hz natural mode. oldlike shows it at 50 Hz (ratio 4.5). No other Arnold-tongue-like structure appears on this grid.
- **After forcing stops.** The local models ring down at about 32 Hz. For local0.1/real at g=40, SD/mean falls 0.48 → 0.12 → 0.04 → 0.016 → 0.006 in successive 100 ms bins, back to baseline within about 400 ms. Nothing persists.
- **Pulse trains (g=80).** Gain is about 2–3 and broad from 5 to 30 Hz, with no sharp resonance. It falls above 35 Hz.
- **Poisson input with sinusoidal forcing (g=80).** The peak is again at 24–27 Hz (local), but entrainment drops to 0.36–0.5 at 10 Hz and 0.83–0.86 at 27 Hz.

**Conclusion:** In the literature-based local model (κ 0–0.1), PN stimulation does *not* elicit a sustained oscillation. This holds for broad or strong drive, for synchronous volleys, and for periodic forcing. What exists is a damped ~30 Hz mode, a resonance/ringing with Q of a few: it rings after a synchronous volley, amplifies about 2× when forced near 24–30 Hz, and follows 10 Hz input without amplification.
- Wiring dependence is weak. At low g, real wiring has the highest Q and gain; at high g the order reverses.
- A sustained oscillation needs strong intra-APL coupling (κ=10, real wiring, g≥80) or the old global model, and in those cases strong drive actually *suppresses* it.

**Caveats:**
- The frequency grid is coarse, so Q_bw is approximate.
- Only one Poisson seed was run.
- Compartment correlation was only measured in Exp 1.
- Stimuli other than the PN set (nested u<frac sets, seed 7) were not tested.
- Only the τ_APL 2 ms / delay 10 ms regime was used.
- "Depth 0.5" refers to rate modulation of the active PNs only.
- Jitter is Gaussian, so at SD 5–10 ms some spikes arrive before the nominal volley time.

## Combined α′β′ model: APL + DPM + APL–DPM gap + DAN→APL (DD2R) + APL octopamine (2026-11-18)
Code: compmb2.py (adds DPM to the network), compsim2.py (model), comb_sweep.py (stages s1/s2/rest/x → comb/*.pkl, 1674 runs), comb_an.py, oa_check.py (oachk/, 33 long 4 s runs), comb_plot.py.
Tables: comb_all.csv, comb_s1_tables.txt, comb_s2_tables.txt, comb_rest_tables.txt, oa_check.csv. Figure: figC1_combined_apb_model.png.
Base model is unchanged (compsim, local0.1): κ=0.1, gkk=2 (inhibitory axonal KC-KC), calyx-only soma inhibition, τ_APL 2 ms, delay 10 ms, A=10. With all new terms off, compsim2 reproduces compsim exactly (APL mean 1.6236 in both).

### Sources checked (abstracts read via Europe PMC; full texts only where noted)
- **Wu et al. 2011, Curr Biol 21:848 (PMID 21530256)**
  - APL and DPM form heterotypic gap junctions within the MB; inx7 is in APL and inx6 in DPM.
  - Knocking them down spares learning and ARM but abolishes ASM.
  - The abstract gives no conductance and no lobe distribution. The full text returned 403.
  - So "concentrated in α′β′" is **taken from the brief and not verified**. It is used only as one of three gap profiles.
- **Haynes et al. 2015, eLife 4:e03868 (full text read)**
  - DPMs are sleep-promoting inhibitory neurons that release GABA onto wake-promoting α′β′ KCs.
  - DPM activation raises chloride in MB neurons, with no detectable rise in Ca²⁺ or cAMP.
  - α′β′ GABA_A (Rdl) and GABA_B-R3 receptors are involved.
  - DPMs are 5-HT positive and TH negative. They are coupled to APL via gap junctions, citing Wu 2011.
  - 5-HT acts on α/β via Gαi-coupled 5HT1A (citing Lee 2011, which I did not read).
  - → DPM→KC is modelled as **inhibitory**, with "none" (neutral) as the control.
  - Note: the MaleCNS consensus_nt for DPM is "dopamine", which conflicts with this immunostaining. I ignore the connectome NT for DPM.
- **Zhou et al. 2019, PNAS 116:5118 (PMID 30796183, abstract only)**
  - Shock-activated DANs suppress APL via DD2R during conditioning.
  - The reduced APL odour response persists after conditioning.
  - The abstract does not name which DAN cluster and gives no numbers.
- **Wu et al. 2013, Curr Biol (PMID 24239122, abstract)**
  - APL is octopamine (OA) immunopositive. OA from APL acts on α′β′ KCs via Octβ2R for ARM, in parallel with serotonin from DPM onto αβ.
  - The abstract gives no time constants or magnitudes.
- **No parameter values are taken from the papers. Every strength and time constant below is an assumption that is swept.**

### Model additions (all assumptions are labelled)
- **DPM**
  - 2 cells, graded, one compartment per ROI, like APL.
  - τ_DPM 5 ms (assumed); intra-DPM coupling κ_d = 0.1, with κ_d = 10 tested as a "compact DPM".
  - Drive: KC→DPM per-ROI synapses from MaleCNS (KC→DPM 95.5k), normalised per compartment, gain = g.
  - Output: through the same 10 ms delay chain, then DPM→KC (MaleCNS per ROI, normalised by KC total input). Summed, these weights are about 0.16 of the APL→KC weights.
  - It acts as an extra presynaptic shunting term on KC axonal output (dk = inh) or is absent (dk = none).
  - Cell pairing from connectome contacts: APL 10540 ↔ DPM 12569 (right hemisphere), APL 10977 ↔ DPM 11734 (left).
- **Gap junction**
  - Current g_gap·w_c·(V_DPM − V_APL) per lobe ROI c, entering both cells.
  - Profiles:
    - "apb": w = 1 in a′L/b′L and 0.1 in the other lobes (brief, unverified).
    - "uniform".
    - "contact": w ∝ APL↔DPM chemical synapse count per ROI, a proxy because gap junctions are not in the connectome. This proxy peaks in γL, not α′β′.
  - g_gap swept 0–30, in units of the APL leak.
- **DAN→APL (post-learning state)**
  - Static multiplicative reduction of APL compartment drive: ×(1 − s·mask), s from 0 to 0.9.
  - Masks:
    - "apb" (a′L, b′L).
    - "ppl1": PPL1→APL per-ROI synapses, extracted from syn-partners into edges_dan_roi.csv and normalised to max = 1. PPL1 types PPL101–107 feed APL mainly in a′L, aL and gL. That PPL1 is the shock-signalling group is my assumption, since Zhou's abstract doesn't name the cluster.
    - "all" lobes.
- **Octopamine**
  - A slow trace OA, with τ 1000 ms (also 100 ms), of the α′β′-ROI APL output divided by its baseline (1.6). OA = 1 at baseline.
  - Two modes:
    - "gain": α′β′ KC axonal output ×(1 + g_oa·OA).
    - "exc": α′β′ KC PN drive ×(1 + g_oa·OA).
  - g_oa swept 0.5–32 (assumed; the sign is chosen from Octβ2R being cAMP-raising).

### Results
Tests used real, within-type and block-shuffled wiring at g 40/80/160. Measures:
- Constant input: sustained check from APL SD/mean over 500–1500 ms; then PN volleys at 1500 and 2000 ms, scored by damped-sinusoid Q.
- Poisson input: compartment correlation, KC sparseness.
- 27 Hz sinusoidal forcing (depth 0.5): gain and post-forcing SD.
- Sustained = SD/mean > 0.05 with ACF(200–400 ms lags) > 0.7.

1. **Gap junction alone (DPM present)**
   - **No sustained oscillation** at any g_gap, profile or wiring. Max det SD/mean is 0.024, and that is block-wiring noise.
   - The gap *damps* the ~30 Hz mode, because DPM acts as an extra capacitive/leak load on APL. Real wiring, g=80:

     | g_gap = 30 | ringing Q (ctrl 4.69) | gain at 27 Hz (ctrl 2.26) |
     |---|---|---|
     | apb profile | 3.69 | 1.70 |
     | uniform | 0.14 (no ringing) | 0.84 |
     | contact | 0.05 (no ringing) | 1.34 |

   - The ringing frequency shifts up slightly, to 31–35 Hz in block wiring.
   - **Effective coupling through DPM** depends on how compact DPM is.
     - With κ_d = 0.1, gap coupling *lowers* APL cross-compartment correlation: Poisson, g=80, real goes from 0.50 to 0.41 (apb 30) and 0.43 (uniform 30).
     - With a compact DPM (κ_d = 10), it raises it to 0.61 (apb 30) and 0.67 (uniform 30); within-cell correlation rises from 0.68 to 0.78 and 0.85.
     - So DPM *can* globalise APL, but every globalising configuration also kills the ringing: Q is 0.15–0.6 with uniform/compact DPM.
   - DPM→KC inhibitory vs none mostly changes Q by ≤10 %. The exception is block wiring, g=160, gap 30, where Q is 3.42 with inhibitory output and 0.04 with none.
   - With very strong gap (30), especially a compact DPM in real wiring, a small fast ~100 Hz component appears (SD/mean ≤0.009 with gap alone, up to 0.16 in the combination of compact DPM + gap 30 + OA 8 + DAN 0.9). It persists when DT is halved, so it is not a simple step-size artefact, but its origin is unresolved. It is not the 30 Hz mode.
2. **DAN suppression alone**
   - **No oscillation** (det max 0.031).
   - Mild damping: real g=80 Q goes 4.69 → 4.66 (apb 0.9), 4.67 (ppl1 0.9) and 3.76 (all 0.9); gain at 27 Hz goes 2.26 → 2.26 and 2.00.
   - Compartment correlation rises slightly (0.50 → 0.53 for apb 0.9).
   - KC sparseness barely changes (fraction active per 50 ms, α′β′, 0.314 → 0.315), because the suppression is local and lobe-only and soma inhibition comes from the calyx.
3. **Octopamine alone**
   - **gain mode, g_oa ≤ 4:** no sustained oscillation (max 0.045). Ringing Q rises in the shuffles (type g80 4.6 → 9.1; block g160 6.9 → 13.0) but not in real wiring (4.69 → 4.11). Gain at 27 Hz rises a little in the shuffles (2.1 → 2.35). Post-forcing SD/mean reaches up to 0.35 (type g80).
   - **gain mode, g_oa ≥ 8–16: sustained limit cycle at 25–30 Hz, but only in shuffled wiring.**
     - Long 4 s deterministic runs: block shows SD/mean 0.32–0.68, ACF 0.85–0.91, f0 25–30 Hz (onset g_oa ≈ 16 at g=80 and ≈ 8 at g=160). Type shows 0.18–0.41, ACF 0.73–0.89, at g_oa 8–32.
     - The frequency falls as g_oa rises.
     - **Real wiring never oscillates.** SD/mean stays ≤0.067 (g=160, g_oa=16, ACF 0.43) up to g_oa = 32. Real wiring also settles at lower OA levels (3–5 vs 7–17).
     - α′β′ APL compartments oscillate 1.1–1.5× more than the other lobes, but the whole APL oscillates (non-α′β′ SD/mean 0.16–0.6). The rhythm is **α′β′-led, not α′β′-confined**.
     - Under Poisson input the same conditions give large but irregular fluctuations at 27–28 Hz (ACF 0.10–0.19), so noise breaks the regularity.
     - **Caveat:** with OA 3–17 these gains multiply α′β′ output by roughly 25–500×, which is unphysiological. Treat this as an existence proof of a loop instability, not a realistic prediction.
   - **exc mode, g_oa ≤ 2:** no oscillation (max 0.040). Gain at 27 Hz drops (2.26 → 1.33). α′β′ KCs become much less sparse (Poisson g40, fraction active per 50 ms 0.43 → 0.69, non-α′β′ 0.39).
4. **Combinations**
   - 27 combinations of gap {0, 3, 30 apb} × DAN {0, 0.6, 0.9 apb} × OA {0, 1, 4}, plus 5 extra combinations: **none sustained**. Max det SD/mean is 0.047, with the ~100 Hz component above being the only exception.
   - Adding gap 30 to OA 4 removes the OA-raised Q (block g80 5.7 → 0.12).
   - OA 8 + DAN 0.9 + gap 3 leaves only block g160 at 0.118 (ACF 0.97); real stays ≤0.035.
   - The "best" combination for oscillation is therefore *strong OA gain without gap coupling*, in shuffled wiring.
5. **Rest-like low drive (Poisson)**
   - Conditions: all PNs at 2 Hz, or 20 % at 10 Hz.
   - Large noise-driven 25 Hz fluctuations: SD/mean 0.45–1.0, compared with 0.29–0.46 for a normal odour.
   - Low ACF (0.17–0.33), and the same with or without DPM (nodpm 0.61–1.00 vs ctrl 0.62–1.01 for all PNs at 2 Hz, real wiring). So there is **no rest-specific limit cycle**.
   - Gap 30 reduces the fluctuations (0.48–0.78 apb; 0.33–0.51 uniform) and moves α′β′ power to about 9–11 Hz, also noise-driven.
6. **Shuffled controls:** done for every condition. The only regular self-sustained 30 Hz rhythm (strong OA gain) occurs in block and type shuffles and not in real wiring.

**Conclusion:** none of the literature-motivated ingredients turns the damped ~30 Hz mode into a sustained rhythm in the real connectome at plausible strengths.
- The gap junction and DAN suppression damp it.
- Octopamine in gain mode sharpens resonance only in shuffled wirings.
- At unphysiologically strong OA gain, shuffled networks enter a 25–30 Hz limit cycle that the real wiring resists.
- DPM globalises APL only when DPM is assumed electrically compact, and then it removes the ringing.

**Caveats:**
- Every new parameter is an assumption. The α′β′ gap profile is unverified, and the gap is represented only by a contact proxy.
- DAN suppression is static.
- OA acts on KC output gain or drive and not on the full Octβ2R/cAMP pathway.
- Only 1 Poisson seed was run.
- The constant-input sustained window is 1 s (4 s for oa_check).
- The ~100 Hz component is unresolved.

## Non-KC presynaptic partners of APL (MaleCNS v1.0; 2026-11-18)
Files:
- Scripts: extract_apl_in.py (scans syn-partners → apl_in_syn.parquet, 243,004 synapses onto the 2 APLs), apl_inputs.py.
- Source table: apl_in_weights.csv (from connectome-weights).
- Output: **apl_nonKC_inputs.csv**, one row per presynaptic type (395 types). Columns:
  - cells, total synapses, synapses to APL_R (10540) and APL_L (10977), % of input
  - synapses and fractions per region (CA, PED, aL, a′L, bL, b′L, gL, outsideMB)
  - number of MB regions holding ≥10 %, effective number of MB regions exp(entropy)
  - main ROIs, NT (consensus and cell-type prediction, plus ground truth where present), flags

Notes on the data:
- The connectome-weights and syn-partners totals agree exactly: 124,656 synapses (R) + 118,348 (L) = 243,004.
- ROI = primary_post. "outsideMB" means any non-MB ROI, including unassigned ones next to the MB.

**Totals**
- KC → APL: 210,352 synapses = **86.6 %** of APL input (R 108,338; L 102,014).
- Non-KC: 32,652 synapses = **13.4 %**, from 8,439 bodies.
  - 7,312 of these bodies are untyped. They carry 9,107 synapses (3.7 %), with a median of 1 and a max of 26 synapses per body, and about 98 % have no annotation row. They are probably small fragments; some could be untraced KC pieces.
- By class:
  - DAN 3.3 % (26 types, 334 cells)
  - ALPN 2.2 % (84 types, 282 cells; 83 % of it in the calyx)
  - MBON 1.0 %
  - DPM 1.45 %
- Non-KC share of APL input per region: CA 22.6 %, PED 5.2 %, aL 9.3 %, a′L 16.9 %, bL 10.0 %, b′L 15.8 %, gL 10.4 %, outsideMB 18.9 %.
- Predicted NT of non-KC input (consensus_nt, a *prediction*): dopamine 4.8 %, unclear 3.7 %, ACh 2.3 %, GABA 1.5 %, glutamate 1.0 %, octopamine 0.12 %, serotonin 0.01 %.

**Top types:** DPM 3,521 (1.45 %); PPL103 1,474; MBON11 1,302; PAM10 891; LHMB1 837; PPL101 810; LHCENT5 662; PPL105 615; PAM02 544; MBON30 491.

**Only DPM and MBON11 spread broadly across MB compartments** (≥4 regions each ≥10 %; effective number of regions about 5).
- DPM: gL 36 %, aL 17 %, bL 11 %, with the remainder in a′L, b′L and PED.
- MBON11 (predicted GABA): aL 29 %, bL 19 %, gL 16 %.
- Most DANs are compartment-specific, e.g. PAM02/05/06 >90 % b′L, PAM04 96 % bL, PAM08/12 >90 % gL, PPL104 79 % a′L.
- Cholinergic input is almost all ALPN, in the calyx.
- Octopaminergic input is small: OA-VPM3 140, OA-VUMa2 107, OA-VPM4 32 synapses. Serotonergic input other than DPM is about 33 synapses (CSD 30 of them).
- Sensory, visual and descending inputs total about 0.08 %.
- DPM's NT prediction is "dopamine", which conflicts with the literature (5-HT/GABA; Haynes 2015). APL–DPM gap junctions are not in the connectome.

## MBON–DAN feedback loop + DA-gated KC→MBON plasticity (mbon_dan/), 2026-11-18

**Step 1: connectome (MaleCNS v1.0, minconf 0.5)**
- Types were mapped to compartments using Aso 2014 Table 1 and Li 2020 (`comps.py`). MBON NT signs come from the literature (Aso 2014); others use consensus_nt, which is a **prediction**. ACh is treated as +, GABA as −, and Glu as a ± parameter.
- Tables: `table_MBON_to_DAN.csv`, `table_DAN_to_MBON.csv`, `table_MBON_to_MBON.csv`, `table_DAN_to_DAN.csv`, `table_MBON_X_DAN_2hop.csv`. Matrices are in `compartment_mats.pkl`. Figure: `figMD1_wiring.png`.
- **Direct MBON→DAN:** 11,020 synapses, which is **2.4 % of all DAN input** (465,242).
  - Composition of all DAN input: KC 60.5 %, other neurons 30.2 %, untyped 3.6 %, MBON 2.4 %, DAN 2.0 %, APL/DPM 1.3 %.
  - Same-compartment 3,133 vs cross-compartment 6,291. The remaining ~1,600 involve unassigned types (PPL107/108, MBON22/23), including MBON04→PPL107 with 671.
- **Top direct pairs:** MBON04(β′2, Glu)→PPL107 671; MBON05(γ4, Glu)→PAM07(γ4) 407; MBON30→PAM08 287; MBON06(β1, Glu)→PAM11(α1) 279; MBON11(γ1pedc, GABA)→PPL101(γ1) 205; MBON16(α′3, ACh)→PPL104(α′3) 160.
- **Known loops are present but small** (% of the DAN type's input): MBON07→PAM11 (α1, Glu) 74 syn / 0.45 %; MBON11→PPL101 205 / 0.51 %; MBON12→PPL103 53 / 0.16 %.
- **Other connection classes:** DAN→MBON 39,616 synapses, 89 % same-compartment. MBON→MBON 26,259 synapses, mostly cross-compartment.

**Step 2: model (`mdmodel.py`)**
- 15 compartments, 2 odors, odor-specific weights w[o,c]. Plasticity rules:
  - Depression: −η·relu(D−θ)·KC·w.
  - Restoration by ongoing DA without KC activity: +η_f·D·(1−KC)(w0−w).
  - Passive recovery: +ρ(w0−w).
- G = 1 means feedback scaled to its connectome fraction of DAN input; base DAN drive = 1.
- **Controls:** 8 column-permutation shuffles (keep each MBON compartment's outputs) and 8 DAN-relabel shuffles.
- **Scans:** `scan_bistab.py` covers 672 parameter sets × 17 wirings × 8 initial conditions under continuous odor (`scan_summary.csv`, `scan_real_vs_shuffle.csv`). `scan_osc.py` re-checks sustained oscillations with a dt check (`scan_osc_summary.csv`).
- **Hysteresis:** continuation from two initial conditions at fixed US levels (`run_hyst2.py`, `hyst2_summary.csv`). The earlier ramp version (`run_hyst.py`) was discarded because it was contaminated by lag and non-steady-state starts.
- **Conditioning protocol:** 3 pairings, 300 s delay, then 20 odor-alone A/B trials (`run_protocol.py`, `protocol_summary.csv`). Figure: `figMD2_dynamics.png`.

**Results** (model behaviour, not evidence about the fly)
- **G ≤ 10: monostable, no oscillations, no difference from the no-feedback case.** Conditioning curves at G ≤ 10 match G = 0 closely.
- **Multistability appears only at G ≥ 30, mostly with Glu inhibitory.** At G = 100 with Glu−, the real wiring was multistable in 96 % of parameter sets vs 30 % (colperm) and 49 % (relabel). Shuffles are multistable too, so this is a matter of degree, not unique to the real wiring.
  - The compartment most often carrying alternative states is γ1, consistent with the MBON11(GABA)→PPL101 disinhibition loop. Next come α3 and β′1.
- **Hysteresis over a US window (real wiring):**
  - Reward, θ = 1, G = 100, Glu−: bistable for u = 0.4–1.6.
  - Punishment, θ = 0.8, G = 30, Glu−: bistable for the full range 0–3 (β′1, β′2, γ4).
- **Sustained oscillations:** only with Glu− and G ≥ 30. Real wiring: 5–15 % of parameter sets; shuffles: 0.3–6 %. The dominant mode is a relaxation cycle between β′1 and α′1/γ2 compartments, with periods of about 10–210 s set by η and ρ, robust to dt.
  - Proposed loop: MBON15(α′1, ACh)→PAM13/14(β′1) (+); MBON09/10(β′1, GABA)→PPL103(α′1/γ2) (−).
  - The cycle can coexist with a stable fixed point.
- **Extinction-resistant "locked" memories at G = 100** (real wiring only; all shuffles extinguish):
  - Punishment, θ = 0.8: γ1, β2 and α3 stay depressed, odor-specifically. The learned index after 20 odor-alone trials stays at 1.54 (it was 2.08 at trial 1).
  - Reward, θ = 1: β′1 is locked, with an index of −0.87 at trial 20, vs ≈ 0 for G = 0 and for shuffles.
- **Caveats:**
  - Rate model with assumed thresholds and rates. Glu sign unknown. Multi-compartment types are split equally.
  - G ≥ 30 means MBON synapses would be ≥ 30× more effective than an average DAN input synapse. Even if KC→DAN input were ignored, the MBON share of non-KC input is only ~6 %.
  - With θ < base, baseline DA depresses any odor, so CS− is also depressed.
  - Without odor there is no MBON drive, so loops cannot hold memory across odor-free delays (no spontaneous KC activity in the model).

## Indirect pathways and effective MBON→DAN gain (mbon_dan/indirect/), 2026-11-18/19

**Connectome**
- **Intermediate set** (`extract.py`, `build.py`): 12,131 bodies that are not MBON, DAN or KC, and that either get ≥5 synapses from MBONs or give ≥5 synapses to DANs. They group into 8,796 type labels, 6,773 of them untyped fragments; untyped fragments carry ~4 % of the 2-step strength.
  - Weights are input fractions, as in Li et al. 2020 (Fig. 26 suppl. 2: DAN-input matrix × MBON-output matrix, each normalised so a neuron's inputs sum to 1).
  - Intermediate transmitters are the consensus_nt **predictions**, taken as the mode over a type's bodies. 6,000 types are "unknown" (mostly fragments) and 718 "unclear"; these get sign 0 in signed analyses.
- **2-step routes** (`routes.py`; tables `routes_2step_all.csv`, `routes_per_compartment.csv`, `routes_top_intermediates.csv`):
  - Routes are diffuse. The top type, CB1357 (ACh), carries 0.0073 summed over all compartment pairs.
  - Next come SMP194 (ACh), SIP030 (ACh), LHAV9a1_b/c (ACh), CRE052 (GABA), CB4159 (Glu), PRW003 (Glu) and LHMB1 (Glu); most are SMP/CRE/SIP/LH types.
  - Per DAN compartment, 2-step strength is 0.2–1.7× the direct strength. α3 is the only compartment where 2-step exceeds direct (1.7×).
  - Li 2020 reports a glutamatergic bias in direct and indirect same-compartment feedback. Otto et al. 2020 (Curr Biol 30:3200) report LH neurons and putative gustatory interneurons relaying indirect MBON feedback to γ5/β′2a DANs.
- **Other recurrent connections:**
  - MBON→MBON signed matrix: spectral radius 0.025 (Glu−) / 0.017 (Glu+), so ≤3 % amplification of MBON changes.
  - DAN→DAN: 0.25 total fraction, mostly within compartment (β′1 0.043, β′2 0.029); spectral radius 0.043. Sign unknown, scanned at ±1.

**G_eff** (`geff.py`, `fig_geff.py` → `geff_table.csv`, `geff_vs_g.csv`, `geff_per_compartment.csv`, `figI1_indirect_gain.png`)
- Assumptions: every neuron is a linear rate unit; Δr_post = g·sign·(input fraction)·Δr_pre, where g is the intermediate gain (g = 1 means input-fraction-proportional).
- Paths: direct + 2-step + 3-step + all orders, with all orders computed as J_DI·g(I − gF_II)⁻¹F_IM. The all-orders series is valid only while g·ρ(F_II) < 1; ρ(F_II) = 0.30 (signed, Glu−), 0.42 (signed, Glu+), 0.56 (unsigned).

| g | Signed, Glu− | Signed, Glu+ | Unsigned upper bound | Spectral-radius ratio |
|---|---|---|---|---|
| 1 | 1.07× | 1.38× | 1.9× | 0.93–1.22 |
| 2 | 1.17× | 2.9× | 2.7× (3-step only) | — |
| 3 | 1.34× | — | 4.2× (3-step only) | — |

- G_eff here is the Σ|T| ratio (total |T| over direct |J|) unless marked as the spectral-radius ratio.
- Adding MBON→MBON and DAN→DAN changes G_eff by <5 %.
- Per compartment (Glu−, g = 2), row gain ratios are 0.9–2.2×: α3 2.2×, γ1 1.55×.
- **G_eff ≈ 30 is not reached** unless the intermediate network sits near its instability (g → 1/ρ ≈ 1.8–3.3). In that regime the response is amplified without bound and depends on fine tuning.

**Model with explicit intermediate units** (`imd.py`)
- Uses the top 300 typed intermediate types by through-flow. At g = 1 they capture 95 % (Glu−) and 86 % (Glu+) of the signed indirect strength of all typed intermediates.
- Equations: I = relu(1 + gI(F_IM M + F_II(I − 1))); D = relu(base + US + G(J_dir M + J_DI(I − 1)) + sdd·J_DD(D − base)); MBON→MBON with gmm.
- Shuffles are applied to the DAN side only:
  - colperm: each column of J_dir and J_DI is permuted separately.
  - relabel: one DAN permutation is applied to J_dir, J_DI and J_DD.
- Glu+ with gI = 4 is unstable (gI·ρ = 1.26) and gives NaN; it is excluded.

**Results**
- **Continuous-odor multistability** (`scan_ind.py`: 384 parameter sets × 17 wirings × 8 initial conditions; `scan_ind_summary.csv`):
  - G = 1 and 3: none for real wiring at any gI (0/…), with Glu ±, sdd ±1/0 and gmm 0/1.
  - G = 10: none at gI = 0–1; 50 % of real-wiring parameter sets at gI = 2 and 25 % at gI = 4 (Glu−), carried by γ1. The γ1 states hold at gI = 2; at gI = 4 the α′/γ2 compartments also take part. Shuffles at G = 10: colperm 0–3 %, relabel 12 %.
  - G = 30: real 100 % (gI 0–2) vs colperm 25–31 % and relabel 62–66 %.
  - Glu+: real wiring is never multistable.
  - Indirect paths at gI = 2 therefore move the γ1 bistability onset from G ≈ 30 down to G ≈ 10, which is still 10× anatomical.
- **Sustained oscillations:** none for real wiring; 3 colperm cases at G = 30, gI = 4 (period ≈ 91 s).
  - In the previous phase they needed η = 5 or ρ = 0.05 settings; this scan used η = 1 and ρ = 0.01 only.
- **Hysteresis** (two-initial-condition continuation; `hyst_ind_summary.csv`): only at G = 30.
  - Punishment, θ = 0.8: u 0–3, in β′1, β′2, γ4 (+α1 at gI = 2).
  - Reward, θ = 1, gI = 2: u 0.3–0.6.
  - None at G ≤ 10, either gI.
- **Conditioning and extinction** (`protocol_ind_summary.csv`):
  - At G ≤ 10, all gI: extinction/forgetting is like the no-feedback case (PI20 ≈ 0).
  - The only extinction-resistant real-wiring memory is reward, θ = 0.8, G = 30, gI = 4: PI20 −0.62 vs PI1 −1.69, locked in γ5. Shuffle means were +0.20 (colperm) and −0.06 (relabel).
- Figures: `figI1_indirect_gain.png`, `figI2_dynamics_indirect.png`.

**Caveats**
- Linear or threshold-linear rate units with input-fraction weights.
- NT signs of intermediates are predictions; many are unknown or unclear and set to 0. Glu sign is unknown.
- Type-level pooling; equal split across compartments.
- Only the top 300 intermediate types are simulated.
- KC→DAN input (60 % of DAN input) is treated as part of the baseline.
- Scans were trimmed for time: protocol runs Glu− only, sdd 0, gI 0/2 (plus 1/4 at G 10/30); hysteresis gI 0/2 only.

## Kitchen-sink model with subtraction/ablation (mbon_dan/kitchen_sink/), 2026-11-19

**Model** (`ks.py`; parameter ranges and their basis in `param_ranges.csv`)
- Compartment rate model (15 compartments, 2 odors), with all DAN-input terms at G = 1 (input-fraction normalisation).
- 18 switchable components:
  - KC→DAN input. Measured share of DAN input per compartment, γ1 … β1: 0.42–0.72 (`kc_dan_fracs.pkl`).
  - DA-facilitated KC→DAN release, the positive KC↔DAN loop of Cervantes-Sandoval 2017.
  - Spontaneous KC activity.
  - Compartmental APL inhibition (+ APL→DAN); DPM modulation of KC output (+ DPM→DAN); APL–DPM gap junction (Wu 2011).
  - Direct MBON→DAN, top-100 intermediate types, MBON→MBON, DAN→DAN.
  - DA-without-odor restoration and potentiation (Cohn 2015, Berry 2018).
  - DAN autoreceptor term; MBON-output short-term depression/facilitation; DAN and MBON adaptation.
  - Hunger and octopamine bias to PAM (Burke 2012).
  - Saturating transfer, either tanh or a logistic curve with slope 1 at baseline (the SIGMOID component).
- Many entries in `param_ranges.csv` are assumptions (marked).
- Detection: 8 initial states per parameter set, odor on (continuous) and odor off (spontaneous KC only). Plasticity rates were multiplied by a common factor so weights converge within the run; this leaves fixed points unchanged. All hits were re-checked at the original rates.

**Results at G = 1, everything on**
- **Saturating (tanh) transfer** (rounds 1, 1s, 2; 1,680 sets):
  - No multistability under any condition.
  - Odor-gated oscillations: 1.3 % of random sets, 14 % in the strong KC–DAN-loop sub-range.
  - Reason: a concave transfer only allows a single stable state. With strong KC→DAN facilitation it runs away to one saturated up-state.
- **Sigmoidal (logistic) DAN transfer** (round 3; 672 sets: 336 in the full ranges, 336 targeted at strong KC→DAN):
  - Odor-on oscillation: 22 % of sets (6.5 % in the full ranges, 37 % targeted). Period median 18 s (range 3.6–82 s), mostly in α′3, α′1, γ1 and α1.
  - Odor-on multistability: 0.6 % (4 sets).
  - **Odor-off: nothing.** No multistability and no oscillation, so no persistent memory states between odors.
- **Oscillation predictors** (AUC vs non-oscillating sets): β_KD 0.73, s_KD 0.72, excitatory DPM 0.67, Dmax 0.62, DAN adaptation 0.59; and low APL inhibition (0.29) and self-excitatory autoreceptor (0.31). MBON-related parameters (Glu sign, gI, STP) sit near 0.5.
- **Hits** (4 bistable, 6 oscillating; `stage3_hits.csv`):
  - All confirmed at the original plasticity rates, except 1 oscillator that stopped oscillating there.
  - Real wiring vs shuffles: identical. Colperm and relabel shuffles keep the phenomenon in 62–100 % of cases.
  - Bistable hits show odor-intensity hysteresis (bistable for odor ≈ 0.6–1.5 in 3 of 4) and US hysteresis over u = 0–2 (3 of 4 for punishment, 2 of 4 for reward).
- **Conditioning** (3 pairings, then tests after 300 s and +1,800 s odor-free gaps, then 6 extinction trials; original rates):
  - Learned index is small (|PI| ≤ 0.2), and essentially zero after the extinction trials.
  - Memory across the gaps follows passive recovery; no bistable persistence.
  - The KC↔DAN up-state depresses CS+ and CS− alike. In one hit, removing KC→DAN raised PI at 300 s from 0.01 to 0.82.

**Ablation** (`ablation_matrix.csv`, `ablation_long.csv`, `leave_one_in_long.csv`, `leave_few_in.csv`)
- **Necessary in all 10 hits:** KD (KC→DAN) and KDfac (DA facilitation of KC→DAN).
- **Necessary in 8 of 10 hits:** SIGMOID (all 4 bistable hits; 4 of 6 oscillators).
- **Necessary for oscillation:** DAN adaptation (all 6 oscillators; 1 of 4 bistable).
- **Context-dependent (needed in some hits only):** APL (needed in 8/10), AUTO (3/10), DPM (5/10), SPONT (3/10), STATE (2/10). These set the loop gain inside its operating window.
- **Never necessary:** direct MBON→DAN, intermediates, MBON→MBON, DAN→DAN, STP, MBON adaptation, restoration/potentiation, APL–DPM gap junction.
- **Sufficiency:**
  - Every hit keeps its phenomenon with all MBON-related pathways removed.
  - Greedy backward elimination leaves KD + KDfac (+ SIGMOID / ADAPT_D) plus 0–4 gain-setting components (APL, AUTO, DPM, SPONT, STATE).
  - Leave-few-in from an all-off core: KD+KDfac+ADAPT_D reproduces 1 of 6 oscillators; KD+KDfac+SIGMOID+ADAPT_D reproduces 3 of 6. Bistability needs its gain-setting components at their sampled values.

**Gain needed for odor-free multistability** (`gscan_summary.csv`; 24 sets)
- Scaling all DAN inputs: multistable fraction 0 / 12 / 38 / 58 / 79 % at G = 1 / 3 / 10 / 30 / 100. Driven mainly by the spontaneous-KC→DAN loop.
- Scaling MBON-derived inputs only: none up to 10×; 8 % at 30×; 12 % at 100×.

**Figure:** `figK1_kitchen_sink.png`.

**Interpretation and caveats**
- At anatomically scaled strength, the phenomena that appear come from the KC↔DAN reciprocal loop (Cervantes-Sandoval 2017) plus DAN nonlinearity and adaptation. They are odor-gated: DAN up-states and relaxation oscillations during odor. The MBON–DAN wiring is not needed.
- Odor-free memory states would need ≥30× MBON-derived gain or ≥3–10× total DAN input gain.
- Key assumptions: KC→DAN efficacy and DA facilitation magnitude (β_KD up to 2); a sigmoidal DAN transfer with baseline on its expansive part; adaptation strength. All type-level and rate-based. Ablation results depend on the sampled hits (10).

## Literature constraints on the KC↔DAN loop (mbon_dan/kc_dan_lit/), 2026-11-19

**Literature search.** Sources: PubMed/PMC full texts, Europe PMC and the publisher PDF, with quotes taken from the paper text. Saved files: `lit_findings.csv` (19 entries with DOIs), `findings_log.md` and `papers/`. Many magnitudes are reported only in figures and were not extracted.
- **(1) KC→DAN efficacy.**
  - Anatomy: in Takemura 2017 the KC→DAN synapses outnumber DAN→KC (5,037 vs 2,982 in α3, 1,699 vs 1,466 in α2, 3,054 vs 2,011 in α1). The MaleCNS input fraction is 0.42–0.72.
  - Function: in Cervantes-Sandoval 2017 the synapses are nAChR-mediated. Mecamylamine blocks up to 60 % (P2X2) or >85 % (optogenetic stimulation) of the KC-evoked DAN response. Kir2.1 silencing of KCs reduces DAN responses to odor and shock. KC input "shapes the magnitude of this chronic activity although it may not generate it."
  - Ueno 2017 (ex vivo): stimulating the antennal lobe alone releases no DA. Release needs coincident antennal-lobe + NMDA/AFV input, and nAChR in MB neurons but not in DANs.
- **(2) DA→KC facilitation.**
  - DA/cAMP effects on KC output are slow, post-pairing, compartment- or lobe-specific and bidirectional. Forskolin facilitation was seen in the γ lobe only (Boto 2014). See also Stahl 2022 (GRAB-ACh), Handler 2019 (DopR1/DopR2) and Zhang & Roman 2013 (Go inhibition of release).
  - No acute gain magnitude was found anywhere.
  - DAN autoreceptors (Saito 2026): Dop1R1 amplifies only low-intensity signals, while Dop2R attenuates high-intensity ones.
- **(3) DAN odor responses.**
  - Riemensperger 2005: DANs are "weakly activated by odor … respond strongly to electric shocks."
  - Mao & Davis 2009: response sizes differ by compartment (α′ tip odor > shock; α tip the reverse). Odor responses decline after CS-only exposure.
  - Huang 2024 (voltage imaging): odor responses are valence-signed. PPL1-α3 sums odor and shock "linearly"; γ1pedc behaves similarly.
  - Zolin 2021: DAN odor responses are gated by behaviour.
- **(4) Ongoing activity and oscillations.**
  - Plaçais 2012: spontaneous, odor-free Ca²⁺ oscillations in PPL1-γ1pedc (MP1) and PPL1-γ2α′1 (MV1), not in α2α′2. Single-fly f0 was 0.05–0.29 Hz; the ensemble f0 was 0.13 Hz after training. Brief TrpA1 activation left sustained activity for ≥45 min.
  - Cohn 2015: ongoing DAN activity is correlated with behavioural state.

**Probes applied to the model** (`lit_probe.py`). Each probe uses naive weights, original rates, 10-s stimuli and shock u = 2:
- **L1, odor/shock:** median PPL1 ratio ≤ 0.5.
- **L2, summation index:** odor+shock response divided by the sum of the separate responses, in [0.75, 1.33] for α3 and γ1.
- **L3, KC-silenced shock response:** ≥ 0.3 of control. L3 is non-discriminating (every set passes).
- The thresholds are our own operationalisation of qualitative statements (an assumption). Sensitivity is in `probe_threshold_sensitivity.csv`.

**Results.**
- **Round-3 sets** (672; `probe_r3_summary.csv`):
  - 55 % pass L1 and L2 (77 % of the full-range sets, 33 % of the targeted strong-loop sets).
  - Only 5 of 146 oscillating sets (3.4 %) and 1 of 4 bistable sets pass. Across thresholds 2–24 % of oscillators pass.
  - 9 of the 10 stage-3 hits fail. All 9 fail L1 (odor/shock ratio 1.0–1.7, i.e. odor alone drives DANs about as strongly as shock). The α3 summation index is sublinear (0.51–0.57) in 6 of them, and supralinear at α3 (1.63) and γ1 (2.05) in 1.
  - The pass rate falls with s_KD·β_KD: 0.86–1.0 for β ≤ 0.5, and 0.16 for s_KD > 0.75 with β > 1.5 (`pass_rate_by_sKD_beta.csv`).
- **Literature-constrained re-scan** (`lit_scan.py`; 384 accepted sets in 8 chunks; acceptance 69–86 % for the full ranges, 27–31 % for the targeted ones):
  - Oscillation during odor: 1.6 % (0 % full ranges, 3.1 % targeted), vs 21.7 % in round 3.
  - Multistability: 0 %. Odor off: 0 % for everything.
  - 5 of the 6 oscillators were confirmed at the original rates (`lit_scan_verify_orig_rates.csv`). Their periods were 2.4–24 s, in γ3, α′2, α1 and β1.
  - All of them have β_KD 1.03–1.80, a magnitude the literature does not support.
- **Figure:** `figL1_lit_constraints.png`.

**Verdicts** (`param_verdicts.csv`):

| Assumption | Verdict |
|---|---|
| KC→DAN input exists | Supported |
| Strong KC→DAN efficacy | Unsupported |
| Acute DA facilitation of KC→DAN | Magnitude unknown; above 1 unsupported |
| S-shaped DAN transfer | Unsupported (data suggest linear or compressive summation) |
| DAN adaptation | Supported qualitatively |
| Model's odor-gated oscillations vs real ones | Do not match: real ones are odor-free and in γ1pedc/γ2α′1; periods overlap |

**Interpretation.**
- In the literature-consistent regime, the KC↔DAN loop is an amplifier, not a generator. Under these constraints the kitchen-sink phenomena almost vanish, apart from rare oscillations that still need a facilitation gain above 1.
- The documented odor-free oscillations and persistence in PPL1-γ1pedc/γ2α′1 must come from another mechanism. Candidates are intrinsic DAN dynamics, or MBON→DAN/GABAergic feedback (Pavlowsky 2018, MP1–MVP2).

**Caveats.**
- The probes are qualitative statements turned into thresholds.
- Shock amplitude is arbitrary in model units.
- No DAN f–I data were found.
- Figure-only magnitudes were not extracted.
- Siju 2020 was read from the abstract only.

## Plaçais 2012 reproduction (mbon_dan/placais/, 2026-11-19 JST)
**Targets** (`targets.csv`, links inside): no odor; MP1=PPL1-γ1pedc=PPL101 and MV1=PPL1-γ2α′1=PPL103 oscillate (single-fly f0 0.05–0.29 Hz, Q≈1–2.5), synchronous; V1=PPL1-α2α′2=PPL105 only noise (Plaçais 2012, doi 10.1038/nn.3055); TrpA1 flies quiet at baseline but a brief activation gives ≥45 min sustained, possibly oscillatory activity (Suppl. Fig 5); MBON11 (MVP2) GABA-B feedback lowers MP1 frequency (Pavlowsky 2018, doi 10.1016/j.cub.2018.04.040), "mechanisms … remain unknown".
**Results** (`placais_results.csv`, fig `figP1_placais.png`):
- The MBON–DAN network (a,c,d,e) never generates the rhythm by itself; an intrinsic slow oscillator (b: self-excitation + adaptation, restricted to PPL101/103 — near-tautological for selectivity) is needed.
- With 10 % heterogeneity between PPL101 and PPL103, synchrony is the bottleneck. The wiring gives PPL101↔103 coupling of only ~0.002–0.007 per unit κ at G=1 (equally strong toward PPL105). Robust matches without extra coupling: 0 % at G 1–10, 1.7 % at G=100.
- Adding a direct coupling ε≥0.05 (gap-junction-like, assumed, no EM evidence) gives a 70–98 % match at G=0–3. Ablations show the network is dispensable (G=0, κ=0, GABA-B, STP and τ_C all leave it unchanged). Minimal mechanism = intrinsic oscillator + direct coupling. Real vs shuffled wiring makes no difference.
- Common upstream noise through the real shared inputs (JDI cosine 0.40 for 101–103 vs 0.07 for 101–105) is selective but too weak: oscillation corr ≤0.07.
- T5 (quiet + switchable oscillation) is impossible in the intrinsic unit alone (0/6084). In the network it appears only at G=100 with slow GABA-B (2/1440; 0/1536 in a targeted G 30–200 rescan). Both sets pass the 200-s pulse → ≥45 min test. In one, removing MBON11 GABA raises f by 50 % (Pavlowsky-consistent); in the other it abolishes persistence. Both are lost at G≤30.
- Caveats: the oscillations are relaxation-like (Q higher than observed); one hemisphere; deterministic; intermediate signs predicted; earlier quiet-init "bistable" hits were exact-fixed-point artefacts (fixed by a perturbed init).

## Gap junctions between PPL101 (MP1) and PPL103 (MV1)? (mbon_dan/gapjunction/, 2026-11-19 JST)
Evidence table: `evidence_table.csv`; figure `figG1_contacts.png`; contacts `contact_summary.csv`.
- **Transcriptomics.** Aso 2019 (GSE139889, TPM): shakB/inx8 is expressed in every PPL1 type (51–166 TPM in clean replicates; KCs 78–111), including V1, so it does not single out the pair. Other innexins are ≈0 or glial contamination. The positive control fails (APL Inx7 = 0, DPM Inx6 = 0), so absence means little. Davie 2018: shakB is detected in 56 % of DANs; other innexins are glial or undetected.
- **Literature.** No paired recording, dye coupling or innexin manipulation in PPL1 or other MB DANs was found. MP1–MV1 synchrony (Plaçais 2012; Berry 2012/2015) is compatible with either coupling or common input.
- **EM (male CNS v1.0, 16-nm segmentation, ≤48 nm apposition).**
  - PPL101–PPL103 same side: 121–159 µm², ~10–40× more than either to PPL105 (2–13 µm²). That selectivity matches the oscillation pattern.
  - The apposition is ~90 % outside the MB (SMP/CRE/tract). Normalised by surface it is ~15–20× lower than the known-GJ APL–DPM pair and below PPL101–PPL102.
  - Contralateral 101–103 apposition is only 2–6 µm². Chemical synapses between 101 and 103 are 0–9.
- **Verdict:** no direct evidence. Expression and anatomy permit shakB-type coupling outside the MB, but nothing demonstrates it, and EM cannot resolve gap junctions.
- **Most decisive experiment:** dual whole-cell recording of MP1 and MV1 (current injection → coupling coefficient, ± carbenoxolone or meclofenamic acid), plus shakB RNAi/CRISPR in MP1/MV1 split-GAL4 lines while imaging spontaneous synchrony. A cheaper first step: neurobiotin fill of MP1, then look for MV1 co-labelling.

## Shared input vs electrical coupling for MP1–MV1 synchrony (gapjunction/, 2026-11-19 JST, light pass)
- **Shared inputs (male CNS, same side).** PPL101 and PPL103 share 1,656 (R) / 1,673 (L) presynaptic bodies (179/208 non-KC), which carry 53–62 % of each neuron's input synapses. Input-weight cosine 0.37–0.41 (`shared_input_stats.csv`; top shared: SMP056, DPM, AVLP563, GNG321, APL).
- **Step 1 (`shared.py`, `shared_input_sync.csv`).** The Plaçais model (111 oscillator sets, 10 % heterogeneity, ε=0, desynchronised start) driven by OU input with correlation c, SD σ ≤0.4 and τ 0.1–10 s.
  - c=0.39 (wiring): 0 % sync at every σ and τ.
  - c=0.7 (wiring plus an assumed shared behavioural-state drive): ≤4 %.
  - c=1 (fully common input): ≤22 %, and median corr ≤0.14 throughout.
  - So shared input alone fails.
- **Step 2 (`gj_bound.py`, `gj_bound.csv`, `figG2_shared_vs_gj.png`).**
  - Formula: Gj = apposition area (159/121 µm²) × plaque fraction (assumed 1e-4–5e-2) × 12,000 channels/µm² (crystalline plaque, https://pmc.ncbi.nlm.nih.gov/articles/PMC1847771/) × open fraction 0.01–0.15 (Bukauskas 2000, https://doi.org/10.1073/pnas.050588497) × unitary conductance 10–500 pS. Connexins are ~10–300 pS; leech innexins reach up to 500 pS (https://pmc.ncbi.nlm.nih.gov/articles/PMC6193117/). No ShakB unitary value has been published.
  - Rin is assumed to be 1 GΩ (0.5–2), using MBON-α3's 990 MΩ (https://www.biorxiv.org/content/10.1101/2020.12.06.413500v1) because no PPL1 value was found.
  - The model's ε=0.02–0.05 needs only Gj ≈ 0.02–0.05 nS, i.e. a few open channels. Any single minimal functional plaque (~300 channels) gives 0.03–22 nS (coupling coefficient 0.03–0.96). Contact area is therefore no constraint: the area allows 10²–10⁵× more conductance than needed.
- **Verdict:** shared input can't synchronise these oscillators; a tiny electrical coupling can, and anatomy permits it. Whether it exists is the open question, which only dual recording or shakB knockdown can answer.
- **Caveats:** ε≈CC assumes rate deviations are linear in somatic voltage and ignores attenuation from the dendritic or tract contact sites; the noise was additive OU only.

## NOTE (2026-11-19 23:35 JST): MP1–MV1 gap junction is a WORKING HYPOTHESIS
The ε coupling between PPL101 (MP1) and PPL103 (MV1) in all later models is an assumption. There is no direct evidence (no recordings, dye coupling or innexin manipulation; EM cannot resolve gap junctions). It is motivated by: shared input fails to synchronise the model; shakB is expressed in PPL1; same-side membrane apposition is selective (121–159 µm²); and a tiny Gj would suffice. See the gapjunction/ sections.

## Behaviour phase: cross-scale chain, connectome → oscillation → memory → T-maze PI (2026-11-19, behavior/)
**Reminder:** the MP1–MV1 gap junction (ε) remains a WORKING HYPOTHESIS. Results that depend on ε are conditional on it.

**Layers**
1. Connectome (male CNS, pm.py).
2. Circuit: PPL101/103 oscillation states for the 111 Plaçais-matching sets, G=1–3 (`circuit_states.py` → `circuit_states.csv`).
3. Memory: assumed ODEs in `xbehav.py`, assumptions A1–A4 listed in its docstring.
   - Ongoing DA drives forgetting (Berry 2012).
   - DA inhibits ARM.
   - DA during the first 10 min of each spaced ITI drives LTM (Plaçais 2012).
   - ARM and LTM are exclusive.
   - Massed training puts the circuit in a weakened-oscillation state (imposed: A1).
4. Readout: KC→MBON CS+ depression through the connectome compartment map A_MD, the MBON–MBON JMM, and NT valence from Aso 2014b (https://doi.org/10.7554/eLife.04580). PI = 100·tanh(βΔ), with β set so that WT 1x immediate PI = 80 (arbitrary scale).
   - Two DA→memory variants: ADD (mean DA) and COI (coincidence ⟨r101·r103⟩).

**Results** (`run_exps.py` → exps.csv / exps_PI.csv; `analyze.py` → predictions_vs_literature.csv and cross_scale_ablation.csv; `readout_abl.py` → readout_ablation.csv; `sens.py` → sensitivity.csv and sensitivity_summary.csv; figure figB1_cross_scale.png)

- **WT protocols:**
  - PI: 1x 0 h 80 → 3 h 44; massed 24 h 69 (ARM); spaced 24 h 89 (LTM, L≈0.62).
  - CXM cuts spaced 24 h to 34. This matches the Tully 1994 qualitative pattern (https://doi.org/10.1016/0092-8674(94)90398-0).

- **Plaçais 2012 / Berry 2012 manipulations** (median ΔPI over 111 sets, ADD; COI was nearly identical):

  | Manipulation | ΔPI | Literature | Verdict |
  |---|---|---|---|
  | P1 block after 1x | +17 | ↑ | ✓ |
  | P2 block after massed | +7 (up in 56 % of sets, down in none) | ↑ | weak ✓ |
  | P3 TrpA1 after 1x | −15 | ↓ | ✓ |
  | P4 TrpA1 after each massed cycle | −29 | ↓ | ✓ |
  | P5 TrpA1 after each spaced cycle | −9 | = | ✗ (mild) |
  | P6 block after spaced | +2, L unchanged | = | ✓ |
  | P7 block during ITIs | −36, L 0.62→0.10 | ↓ | ✓ |

  - The directions of P1–P4 and P7 held under every ×0.5/×2 single-parameter perturbation; 21 sets were tested.
  - **Caveat:** P1–P7 are largely BUILT IN by the assumed memory rules, so this is a consistency check, not an independent prediction.

- **Micro features that carry through to behaviour** (cross_scale_ablation.csv):
  - **ε (hypothetical gap junction):**
    - Circuit effect: synchrony is lost (corr 0.94→0) and coincidence C falls to ×0.29, while mean DA is unchanged.
    - ADD variant: no behavioural effect (ΔPI 0).
    - COI variant: spaced-LTM component halves (L 0.62→0.32); 24 h PI −7 (down in 77 % of sets); 1x 3 h PI +6 (extra ARM).
    - A tonic control with the same mean and no rhythm gives the same effect as ε=0. So in the COI variant it is synchrony, not DA amount, that carries to behaviour.
    - Fragility: the sign of the PI change flips under kL×0.5 or window×0.5 because ARM compensates. The LTM-component change itself is robust.
  - **Intrinsic oscillator removed:** LTM = 0 and memory becomes all ARM. PI rises by +6 to +18 (Berry 2012–like). This is a prediction: memory would become CXM-insensitive.
  - **MBON11→PPL101 feedback removed, and DAN-row wiring shuffles (3 shuffles):** no change at the circuit level (G=1–3), therefore no change in behaviour.
    - This does NOT reproduce Pavlowsky 2018 (MBON11 block impairs appetitive LTM; https://doi.org/10.1016/j.cub.2018.04.040). The model is aversive-only, and its MBON11 effect is negligible at G≤3.
  - **Readout wiring:**
    - The real A_MD compartment map gives a 2.3× larger aversive drive than row-shuffled maps (p≈0.02, 50 perms).
    - The real NT valence gives 2.3× more than shuffled valence (p≈0.02).
    - MBON–MBON JMM matters little (−2 %).
    - Per compartment: γ2α′1 and α′2α2 traces drive more of the PI than γ1pedc. γ1pedc mainly acts through the approach MBON11.

**Interpretation**
- The cross-scale order that survives is: connectome compartment/valence map, then PPL1 oscillation (an intrinsic oscillator plus ε synchrony), then the ARM-vs-LTM balance, then PI.
- Whether ε matters behaviourally depends entirely on whether downstream plasticity reads coincidence or mean DA. That is a testable split: block innexins in MP1/MV1, then measure LTM CXM-sensitivity.

**Caveats**
- Memory-layer forms and constants are assumed.
- The protocol→circuit-state mapping is imposed (A1).
- Aso 2014b valence is extrapolated to MBONs it did not test; atypical MBONs are set to 0.
- PI scale is arbitrary.
- Aversive conditioning only.
- G≥10 regimes, where MBON11 matters, were not used.

## Robot phase: "memory bug robot" (idea #1), end-to-end simulation (2026-11-20 JST, robot_sim/)

**Platform:** fly-car (public repo https://github.com/hamling-ling/fly-car; read-only clone on the box; the user's PC was not touched) on an Arduino UNO Q (STM32U585 M33 160 MHz, 786 kB SRAM, 2 MB flash; https://docs.arduino.cc/hardware/uno-q/).

**Model** (`mbrobot.py`; full details in DESIGN.md):
- Sensing and coding: per-eye colour → 9 PNs → 100 KCs (4 claws, k-WTA 10 %).
- DANs: reduced PPL101/103 oscillator (`dan2.py`). It matches the full pm network within ~3 % on A, C and corr for on / eps0 / bias −0.5 (`dan2_validation.csv`).
- Memory: S, ARM and LTM traces following the `xbehav` rules.
- Readout: connectome-derived compartment gains g = 0.21/0.46/0.33.
- Motor: innate crossed light approach plus learned ipsilateral avoidance.
- Training: US = bump into the CS+ lamp stand.
- **TIME COMPRESSION K = 60** (1 robot-s = 1 bio-min, so 24 h = 24 robot-min). The oscillator runs in real time.
- MCU cost: ~9.6 k flops per step at 50 Hz (≈0.3 % of the M33) and ~4.5 kB of state (`cost.txt`).

**Results** (`results.csv`, `summary_by_condition.csv`; 10 seeds × 40 test trials; each seed has its own oscillator set, KC wiring and noise). PI = 100·(CS− − CS+)/(choices); no-choice rate 2 %.

- Naive PI: −4 ± 18 (SD across seeds).
- Intact model, COI variant (mean ± SEM):

  | Protocol | 1 h | 3 h | 24 h | 72 h |
  |---|---|---|---|---|
  | 1x | 50 ± 9 | 43 ± 7 | 41 ± 6 | 10 ± 4 |
  | massed | 96 ± 1 | 96 ± 1 | 89 ± 4 | 45 ± 5 |
  | spaced | 90 ± 2 | 88 ± 4 | 85 ± 6 | 70 ± 5 |

- Spaced vs massed: 72 h difference +25 (Wilcoxon p = 0.002). At 24 h there is no difference (p = 0.47), because PI is near ceiling and massed ARM is still strong.
- Memory type: massed memory is all ARM (0.24 at 24 h); spaced memory is LTM (0.23 at 24 h).
- Bumps per CS+ trial fall from 6.2 to 1.6 (massed) and from 6.2 to 2.7 (spaced). This is self-limiting avoidance learned during training.

**Ablations** (paired by seed, COI variant):
- **ε = 0:**
  - Spaced: PI −18 / −27 / −31 at 1 / 24 / 72 h (p ≤ 0.008); LTM falls 0.23 → 0.07.
  - Massed: no effect.
  - 1x: +4 to +6 (extra ARM).
  - ADD variant: no ε effect at all, a dependency carried over from xbehav.
- **Oscillator off:**
  - Spaced: LTM = 0 and memory becomes all ARM. Early PI is slightly higher (+5); 72 h PI is −24.5 (p = 0.002).
  - 1x: +8 to +13.
- **No learning:** PI ≈ 0 throughout.

**Caveats**
- All memory and motor constants are assumed. kL was ×4 versus xbehav so that compressed spaced LTM is visible.
- The spacing gate was made causal.
- The massed-fatigue state is imposed (A1).
- The oscillator period is not compressed, so it lasts ~11 bio-min.
- Test trials run on cloned brains (no extinction, no elapsed test time). In hardware, each test trial would take ~45 bio-min and would also act as extinction.
- ε is the gap-junction WORKING HYPOTHESIS. Its behavioural effect requires the COI variant.
- Sensors are idealised; this is not a camera model. Light source and arena are idealised.

**Files:** figR1_memory_bug_robot.png, robot_demo.gif, DESIGN.md (hardware mapping), code (mbrobot.py, dan2.py, run_all.py, demo.py, fig_robot.py, anim.py, cost.py).
