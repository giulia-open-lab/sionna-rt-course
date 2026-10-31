"""Helpers of Lab 3 "Characterizing two cities with ray tracing": the two cities (and Florence for
Exercise 6) and their small cell, the height map, random outdoor receivers, the paths of each
receiver, small cells and their channel impulse response (CIR), the 3GPP TR 38.901 UMi model, the
plots and the table of results.

The notebook imports them with `from lab3_helpers import *` (this file and lab_helpers.py must be
next to it). The analysis itself is in the cells of the notebook. If you modify this file, restart
the kernel.
"""
import matplotlib.pyplot as plt
import mitsuba as mi
import numpy as np
import sionna.rt
from sionna.rt import Camera, PlanarArray, Transmitter, Receiver, load_scene

from lab_helpers import db, mechanism, paths_of_rx, watt_to_dbm

__all__ = ["CITIES", "ALL_CITIES", "R", "RX_HEIGHT", "TX_HEIGHT", "P_TX_DBM", "THRESHOLD_DBM",
           "UMI", "db", "watt_to_dbm", "load_city", "building_objects", "materials_of",
           "height_map", "distance_to", "outdoor_pixels", "add_random_receivers", "add_receivers",
           "path_arrays", "set_small_cells", "best_server", "sir_db", "umi_path_loss",
           "umi_los_probability", "city_camera", "show_city", "show_radio_maps",
           "plot_los_probability", "plot_path_loss", "plot_cdf", "plot_cir",
           "plot_frequency_response", "RESULTS", "record", "show_results", "show_studies"]

# The two cities: the Sionna scene, the name of its ground object, the site of the small cell (a
# central open square: the Etoile in Paris, the Marienhof in Munich)
CITIES = {"Paris": dict(scene="etoile", ground="Plane", site=(-40.0, 20.0)),
          "Munich": dict(scene="munich", ground="ground", site=(39.0, 76.0))}
# Exercise 6 can also use Florence, the other city of Sionna RT with flat ground (site: an open square)
ALL_CITIES = {**CITIES, "Florence": dict(scene="florence", ground="ground", site=(30.0, -60.0))}
R = 250.0              # radius of the studied area around the small cell [m]
RX_HEIGHT = 1.5        # height of the receivers and of the radio maps [m]
TX_HEIGHT = 10.0       # height of the small cell [m], below the roofs
P_TX_DBM = 30.0        # transmit power [dBm]
THRESHOLD_DBM = -90.0  # coverage threshold P_R,min [dBm]

# 3GPP TR 38.901 (Release 19), urban micro-cell street canyon (UMi) at 3.5 GHz: path-loss slopes
# (10 alpha), shadow fading and median delay spreads
UMI = {"alpha_LoS": 2.1, "alpha_NLoS": 3.53, "sigma_LoS": 4.0, "sigma_NLoS": 7.82,
       "tau_rms_LoS_ns": 40.0, "tau_rms_NLoS_ns": 97.0}


def load_city(city, frequency_ghz=3.5, tx_height=TX_HEIGHT):
    # The city with isotropic vertically polarized antennas and the small cell on its square
    info = ALL_CITIES[city]
    scene = load_scene(getattr(sionna.rt.scene, info["scene"]), merge_shapes=True)
    scene.frequency = frequency_ghz * 1e9
    scene.tx_array = PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
    scene.rx_array = PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
    x, y = info["site"]
    scene.add(Transmitter(name="tx", position=[x, y, tx_height], power_dbm=P_TX_DBM, display_radius=4.0))
    return scene


def building_objects(scene, city):
    # The objects of the scene except the ground: walls and roofs of the buildings
    return [obj for name, obj in scene.objects.items() if name != ALL_CITIES[city]["ground"]]


def materials_of(city):
    # Number of objects of each radio material (walls and roofs are separate objects)
    scene = load_scene(getattr(sionna.rt.scene, ALL_CITIES[city]["scene"]), merge_shapes=False)
    counts = {}
    for obj in scene.objects.values():
        counts[obj.radio_material.name] = counts.get(obj.radio_material.name, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def height_map(scene, pixel=2.0):
    # Height of the top surface on a grid of square pixels (vertical rays cast from above): 0 on the
    # ground, the roof height on a building. Returns the x and y of the pixel centres and the heights.
    bb = scene.mi_scene.bbox()
    xs = np.arange(bb.min.x + pixel / 2, bb.max.x, pixel)
    ys = np.arange(bb.min.y + pixel / 2, bb.max.y, pixel)
    X, Y = np.meshgrid(xs, ys)
    top = float(bb.max.z) + 10.0
    origins = mi.Point3f(X.ravel().astype(np.float32), Y.ravel().astype(np.float32),
                         np.full(X.size, top, dtype=np.float32))
    hit = scene.mi_scene.ray_intersect(mi.Ray3f(origins, mi.Vector3f(0.0, 0.0, -1.0)))
    z = top - hit.t.numpy()
    z[~np.isfinite(z)] = 0.0
    return xs, ys, np.maximum(z, 0.0).reshape(X.shape)


def distance_to(x, y, center):
    # Horizontal distance [m] of the points (x, y) from center = (x0, y0); x and y are broadcast
    return np.hypot(np.asarray(x) - center[0], np.asarray(y) - center[1])


def _outdoor(scene, x, y):
    # True for the points (x, y) where a vertical ray cast from above reaches the ground (no building)
    x, y = np.asarray(x, dtype=np.float32), np.asarray(y, dtype=np.float32)
    top = float(scene.mi_scene.bbox().max.z) + 10.0
    origins = mi.Point3f(x.ravel(), y.ravel(), np.full(x.size, top, dtype=np.float32))
    hit = scene.mi_scene.ray_intersect(mi.Ray3f(origins, mi.Vector3f(0.0, 0.0, -1.0)))
    return (hit.t.numpy() >= top - RX_HEIGHT).reshape(x.shape)


def outdoor_pixels(scene, rm, center, r_min=20.0, r_max=R):
    # Pixels of a radio map that are outdoors and between r_min and r_max from the small cell.
    # Returns the mask and the horizontal distance of every pixel.
    c = rm.cell_centers.numpy()
    d = distance_to(c[..., 0], c[..., 1], center)
    return _outdoor(scene, c[..., 0], c[..., 1]) & (d >= r_min) & (d <= r_max), d


def add_random_receivers(scene, center, n=150, r_min=20.0, r_max=R, seed=1):
    # n receivers at RX_HEIGHT, uniform over the outdoor area between r_min and r_max from center.
    # Returns their (x, y) positions.
    rng = np.random.default_rng(seed)
    points = np.empty((0, 2))
    while len(points) < n:
        r = r_max * np.sqrt(rng.uniform((r_min / r_max) ** 2, 1.0, 4 * n))
        phi = rng.uniform(0.0, 2 * np.pi, 4 * n)
        x, y = center[0] + r * np.cos(phi), center[1] + r * np.sin(phi)
        keep = _outdoor(scene, x, y)
        points = np.vstack([points, np.c_[x[keep], y[keep]]])
    points = points[:n]
    add_receivers(scene, points)
    return points


def add_receivers(scene, points):
    # One receiver at RX_HEIGHT at each point (x, y): rx0, rx1, ...
    for k, (x, y) in enumerate(points):
        scene.add(Receiver(name=f"rx{k}", position=[float(x), float(y), RX_HEIGHT], display_radius=2.0))


def path_arrays(paths):
    # The paths of every receiver (one transmitter, single antennas), as arrays of shape
    # [receivers, paths]: complex coefficients a, delays tau [s], valid (False for empty slots), and
    # los: True for the receivers with a line-of-sight path
    a, tau = paths.cir(normalize_delays=False, out_type="numpy")
    a, tau = a[:, 0, 0, 0, :, 0], tau[:, 0, :]
    valid = paths.valid.numpy()[:, 0, :]
    no_interaction = (paths.interactions.numpy()[:, :, 0, :] == 0).all(axis=0)
    los = (no_interaction & valid).any(axis=1)
    return np.where(valid, a, 0), np.where(valid, tau, np.nan), valid, los


def _roof_height(scene, x, y):
    # Height [m] of the highest surface at (x, y) seen from above: a roof, or 0 on the ground
    top = float(scene.mi_scene.bbox().max.z) + 10.0
    ray = mi.Ray3f(mi.Point3f(float(x), float(y), top), mi.Vector3f(0.0, 0.0, -1.0))
    t_hit = float(scene.mi_scene.ray_intersect(ray).t.numpy()[0])
    return max(0.0, top - t_hit) if np.isfinite(t_hit) else 0.0


def set_small_cells(scene, positions, powers_dbm=P_TX_DBM):
    # Replace the transmitters of the scene with one small cell per position, (x, y, z) or (x, y) at
    # TX_HEIGHT, with its transmit power [dBm] (one value per small cell, or one for all): tx0, tx1, ...
    powers = np.broadcast_to(np.asarray(powers_dbm, dtype=float), (len(positions),))
    for name in list(scene.transmitters):                # one name at a time: sionna-rt 2.0 accepts no list
        scene.remove(name)
    for k, (position, power) in enumerate(zip(positions, powers)):
        x, y, z = position if len(position) == 3 else (*position, TX_HEIGHT)
        if z < _roof_height(scene, x, y):
            print(f"Warning: small cell {k + 1} at ({x:g}, {y:g}, {z:g}) m is inside a building")
        scene.add(Transmitter(name=f"tx{k}", position=[float(x), float(y), float(z)], power_dbm=float(power),
                              display_radius=4.0))


def best_server(rm, points, positions):
    # For each point (x, y): the index of the small cell with the strongest power in the pixel of the
    # point in the radio map rm; where no small cell reaches that pixel, the nearest small cell
    c = rm.cell_centers.numpy()
    j = np.abs(points[:, 0][:, None] - c[0, :, 0][None, :]).argmin(axis=1)   # column: the nearest x
    i = np.abs(points[:, 1][:, None] - c[:, 0, 1][None, :]).argmin(axis=1)   # row: the nearest y
    rss = rm.rss.numpy()[:, i, j]                                          # [small cells, points]
    xy = np.asarray(positions, dtype=float)[:, :2]
    nearest = np.hypot(points[:, None, 0] - xy[None, :, 0], points[:, None, 1] - xy[None, :, 1]).argmin(axis=1)
    return np.where(rss.max(axis=0) > 0, rss.argmax(axis=0), nearest)


def sir_db(rss):
    # Signal-to-interference ratio [dB] of every pixel when the transmitters of rss [transmitters, rows,
    # columns] (W) share one carrier: the power of the best server over the sum of the others
    best = rss.max(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10 * np.log10(best / (rss.sum(axis=0) - best))


def umi_path_loss(d3, frequency_ghz=3.5, los=True, h_bs=TX_HEIGHT, h_ut=RX_HEIGHT):
    # Path loss [dB] of 3GPP TR 38.901 UMi street canyon at 3D distance d3 [m] (section 7.4.1)
    d3 = np.asarray(d3, dtype=float)
    fc = frequency_ghz
    d_bp = 4 * (h_bs - 1.0) * (h_ut - 1.0) * fc * 1e9 / 299792458.0
    pl1 = 32.4 + 21.0 * np.log10(d3) + 20.0 * np.log10(fc)
    pl2 = 32.4 + 40.0 * np.log10(d3) + 20.0 * np.log10(fc) - 9.5 * np.log10(d_bp ** 2 + (h_bs - h_ut) ** 2)
    pl_los = np.where(d3 < d_bp, pl1, pl2)
    if los:
        return pl_los
    pl_nlos = 35.3 * np.log10(d3) + 22.4 + 21.3 * np.log10(fc) - 0.3 * (h_ut - 1.5)
    return np.maximum(pl_los, pl_nlos)


def umi_los_probability(d2):
    # Probability of line of sight of 3GPP TR 38.901 UMi at horizontal distance d2 [m] (section 7.4.2)
    d2 = np.asarray(d2, dtype=float)
    return np.where(d2 <= 18.0, 1.0, 18.0 / np.maximum(d2, 1e-9) + np.exp(-d2 / 36.0) * (1 - 18.0 / np.maximum(d2, 1e-9)))


def city_camera(city, height=420.0):
    # A camera above the small cell, looking down at the studied area
    x, y = ALL_CITIES[city]["site"]
    return Camera(position=[x, y - 330.0, height], look_at=[x, y, 0.0])


def show_city(ax, city, xs, ys, heights):
    # Top view of a height map, with the small cell and the circle of radius R
    x, y = ALL_CITIES[city]["site"]
    im = ax.imshow(np.where(heights > 0, heights, np.nan), origin="lower", cmap="viridis", vmin=0, vmax=40,
                   extent=[xs[0], xs[-1], ys[0], ys[-1]])
    ax.add_patch(plt.Circle((x, y), R, fill=False, color="r", ls="--"))
    ax.plot(x, y, "r^", ms=9)
    ax.set(xlim=(x - 1.2 * R, x + 1.2 * R), ylim=(y - 1.2 * R, y + 1.2 * R), xlabel="x [m]", ylabel="y [m]",
           title=f"{city}: buildings (height), small cell and studied area")
    plt.colorbar(im, ax=ax, shrink=0.8, label="building height [m]")


def show_radio_maps(maps, title="received power P_R [dBm]", sites=None):
    # One top view per city: maps = {city: (prx_dbm, rm, mask)}, pixels outside the mask in white; the
    # small cell on the square, or the numbered sites = {city: [(x, y), ...]}
    fig, axes = plt.subplots(1, len(maps), figsize=(7.2 * len(maps), 5.6), squeeze=False)
    for ax, (city, (prx, rm, mask)) in zip(axes[0], maps.items()):
        c = rm.cell_centers.numpy()
        half = (c[0, 1, 0] - c[0, 0, 0]) / 2
        extent = [c[0, 0, 0] - half, c[0, -1, 0] + half, c[0, 0, 1] - half, c[-1, 0, 1] + half]
        shown = np.where(mask & np.isfinite(prx), prx, np.nan)
        im = ax.imshow(shown, origin="lower", extent=extent, vmin=-130, vmax=-30, cmap="viridis")
        ax.imshow(np.where(mask, np.nan, 1.0), origin="lower", extent=extent, cmap="Greys", vmin=0, vmax=1.6)
        for k, site in enumerate(sites[city] if sites else [ALL_CITIES[city]["site"]]):
            x, y = site[0], site[1]                    # sites (x, y) or (x, y, z)
            ax.plot(x, y, "r^", ms=9)
            if sites:
                ax.annotate(str(k + 1), (x, y), xytext=(5, 4), textcoords="offset points", color="r",
                            fontweight="bold")
        ax.set(title=f"{city}: {title}", xlabel="x [m]", ylabel="y [m]")
        ax.grid(False)
        plt.colorbar(im, ax=ax, shrink=0.8, label="P_R [dBm]")
    fig.tight_layout()
    plt.show()


def plot_los_probability(curves, bins):
    # curves = {city: LoS share [%] in each distance bin}; with the 3GPP UMi model
    centers = (np.asarray(bins[:-1]) + np.asarray(bins[1:])) / 2
    d = np.linspace(bins[0], bins[-1], 200)
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for city, share in curves.items():
        ax.plot(centers, share, "o-", label=city)
    ax.plot(d, 100 * umi_los_probability(d), "k--", label="3GPP UMi")
    ax.set(xlabel="distance from the small cell [m]", ylabel="outdoor area in LoS [%]", ylim=(0, 105),
           title="Probability of line of sight vs distance")
    ax.legend()
    plt.show()


def plot_path_loss(data, frequency_ghz=3.5):
    # data = {city: dict(d=3D distances, pl=path losses [dB], los=bool mask, fits={"LoS": (alpha, sigma, pl0), ...})}
    fig, axes = plt.subplots(1, len(data), figsize=(7.2 * len(data), 4.6), squeeze=False, sharey=True)
    d = np.logspace(np.log10(20), np.log10(R), 100)
    for ax, (city, v) in zip(axes[0], data.items()):
        for los, color, label in ((True, "C0", "LoS"), (False, "C1", "NLoS")):
            sel = v["los"] == los
            ax.semilogx(v["d"][sel], v["pl"][sel], ".", ms=1.5, color=color, alpha=0.4, label=f"{label} pixels")
            if label in v["fits"]:
                alpha, sigma, pl0 = v["fits"][label]
                ax.semilogx(d, pl0 + 10 * alpha * np.log10(d), "-", color=color, lw=2,
                            label=f"fit {label}: alpha {alpha:.2f}, sigma {sigma:.1f} dB")
            ax.semilogx(d, umi_path_loss(d, frequency_ghz, los), "--", color=color, lw=1.5, label=f"3GPP UMi {label}")
        ax.set(title=f"{city}: path loss of the outdoor pixels", xlabel="3D distance [m]", ylabel="path loss [dB]",
               ylim=(50, 180))
        ax.legend(fontsize=7)
    fig.tight_layout()
    plt.show()


def plot_cdf(samples, xlabel, references=None, ax=None, title=None):
    # Empirical cumulative distributions: samples = {label: values}; references = {label: x} as lines.
    # With ax, draws in that panel of an existing figure (shown by the caller)
    show = ax is None
    if show:
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for label, v in samples.items():
        v = np.sort(np.asarray(v)[np.isfinite(v)])
        if len(v):
            ax.step(v, np.arange(1, len(v) + 1) / len(v), where="post", label=f"{label} ({len(v)})")
    for label, x in (references or {}).items():
        ax.axvline(x, color="0.4", ls=":", lw=1)
        ax.text(x, 0.02, label, rotation=90, fontsize=7, va="bottom")
    ax.set(xlabel=xlabel, ylabel="cumulative probability", ylim=(0, 1.02), title=title)
    ax.legend(fontsize=8)
    if show:
        plt.show()



def plot_cir(ax, paths, power_dbm, k):
    # CIR from small cell k to the receiver of a scene with one transmitter: the received power of each
    # path [dBm] at its delay [ns], one colour per mechanism; prints the share of the power of each one
    a, tau, types = paths_of_rx(paths, 0)
    if len(a) == 0:
        print(f"small cell {k + 1}: no path")
        return
    kind = np.array([mechanism(t) for t in types])        # "L", "R", "D" or "S" for each path
    p = np.abs(a) ** 2
    shares = []
    names = (("L", "LoS"), ("R", "reflection"), ("D", "diffraction"), ("S", "scattering"))
    for c, (letter, name) in enumerate(names):
        sel = kind == letter
        if sel.any():
            markers, stems, _ = ax.stem(1e9 * tau[sel], power_dbm + 10 * np.log10(p[sel]), linefmt=f"C{c}-",
                                        markerfmt=f"C{c}" + "osD^v"[k % 5], basefmt=" ", bottom=-160,
                                        label=f"small cell {k + 1}: {name}")
            markers.set_markersize(3)
            stems.set_linewidth(0.8)
        shares.append(f"{name} {100 * p[sel].sum() / p.sum():.0f} %")
    print(f"small cell {k + 1}: {len(a)} paths; share of the power: " + ", ".join(shares))
    ax.set(xlabel="delay [ns]", ylabel="received power of the path [dBm]", ylim=(-160, None))


def plot_frequency_response(ax, paths, power_dbm, k, band_mhz, b_c):
    # Frequency response from small cell k to the receiver of a scene with one transmitter: the received
    # power P_T |H(f)|^2 [dBm] over band_mhz around the carrier, with H(f) = sum_i a_i exp(-j 2 pi f tau_i),
    # the Fourier transform of the CIR; the coherence bandwidth b_c [Hz] as a shaded band
    a, tau, _ = paths_of_rx(paths, 0)
    if len(a) == 0:
        return
    f = np.linspace(-band_mhz / 2, band_mhz / 2, 1001) * 1e6
    t = tau - tau.min()
    h = np.zeros(len(f), dtype=complex)
    for start in range(0, len(a), 1000):                 # 1000 paths at a time, to save memory
        h += np.exp(-2j * np.pi * np.outer(f, t[start:start + 1000])) @ a[start:start + 1000]
    color = f"C{k + 4}"
    ax.plot(f / 1e6, power_dbm + 10 * np.log10(np.abs(h) ** 2), color=color, lw=1,
            label=f"small cell {k + 1}: B_C = {b_c / 1e6:.1f} MHz")
    if np.isfinite(b_c):
        ax.axvspan(-b_c / 2e6, b_c / 2e6, color=color, alpha=0.15)
    ax.set(xlabel="frequency from the carrier [MHz]", ylabel="received power P_T |H(f)|^2 [dBm]",
           xlim=(-band_mhz / 2, band_mhz / 2))


RESULTS = {}   # {quantity: {city: value}}: the numbers of the synthesis table


def record(city, quantity, value):
    RESULTS.setdefault(quantity, {})[city] = value


def show_results():
    '''Print the table of results: one row per quantity, one column per city.'''
    cities = list(CITIES)
    width = max([len(q) for q in RESULTS] + [8])
    print(f"{'':{width}}  " + "  ".join(f"{c:>10}" for c in cities))
    for q, values in sorted(RESULTS.items(), key=lambda row: row[0] != "frequency [GHz]"):   # the frequency first
        cells = [values.get(c) for c in cities]
        text = [f"{v:>10.1f}" if isinstance(v, (int, float, np.floating)) else f"{str(v):>10}" for v in cells]
        print(f"{q:{width}}  " + "  ".join(text))


def show_studies(studies):
    '''Print the coverage of Exercise 5: the reference of Exercise 2, then one row per change, each with
    its carrier frequency.'''
    cities = list(CITIES)
    reference = RESULTS["frequency [GHz]"][cities[0]]
    rows = [("none (Exercise 2)", reference, "coverage [%]")]
    rows += [(study, change.get("frequency_ghz", reference), f"coverage, {study} [%]")
             for study, change in studies.items()]
    width = max(len(label) for label, _, _ in rows)
    print("coverage [%] with one change at a time")
    print(f"{'change':{width}}  {'frequency [GHz]':>15}  " + "  ".join(f"{c:>10}" for c in cities))
    for label, frequency, key in rows:
        print(f"{label:{width}}  {frequency:>15.1f}  " + "  ".join(f"{RESULTS[key][c]:>10.1f}" for c in cities))
