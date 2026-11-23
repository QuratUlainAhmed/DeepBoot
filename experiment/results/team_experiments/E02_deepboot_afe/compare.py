import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = "experiment/results/team_experiments/"
E01 = R + "E01_deepboot_baseline/"
E02 = R + "E02_deepboot_afe/"

def jcts(p):
    d = json.load(open(p + "summary.json"))["jcts"]
    return {k: v for k, v in d.items() if not k.startswith("inference-")}

def train(p):
    jobs = json.load(open(p + "jobinfo.log"))["submitted_jobs"]
    return [j for j in jobs if j["num_restarts"] is not None]

a, b = jcts(E01), jcts(E02)
names = [n for n in a if n in b]
fig, ax = plt.subplots(1, 3, figsize=(15, 4.5))

ax[0].scatter([a[n] for n in names], [b[n] for n in names], s=12)
m = max(max(a.values()), max(b.values()))
ax[0].plot([1, m], [1, m], "k--", lw=1)
ax[0].set_xscale("log"); ax[0].set_yscale("log")
ax[0].set_xlabel("E01 JCT (s)"); ax[0].set_ylabel("E02 JCT (s)")
ax[0].set_title("Per-job training JCT (below line = faster with AFE)")

t1, t2 = train(E01), train(E02)
labels = ["E01 (AFE off)", "E02 (AFE on)"]
delay = [sum(j["delay_time"] for j in t) for t in (t1, t2)]
ax[1].bar(labels, delay, color=["tab:gray", "tab:green"])
ax[1].set_ylabel("Total delay paid (s)")
ax[1].set_title("Restart/rescale delay, 160 training jobs")

per = [d / sum(j["num_restarts"] for j in t) for d, t in zip(delay, (t1, t2))]
ax[2].bar(labels, per, color=["tab:gray", "tab:green"])
ax[2].set_ylabel("Seconds per restart")
ax[2].set_title("Delay per restart")

plt.tight_layout()
plt.savefig(E02 + "e01_vs_e02.png", dpi=150)
print("saved", E02 + "e01_vs_e02.png")
