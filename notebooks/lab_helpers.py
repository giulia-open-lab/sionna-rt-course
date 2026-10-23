"""Helpers of the lab "Exploring radio propagation with Sionna RT": the street-canyon scene and
its receivers, the ground mesh, the reflection coefficient of the ground, the fit of the path-loss
exponent, the outdoor mask, map drawing, sweeps and logs.

The notebook imports them with `from lab_helpers import *` (this file must be next to it). The
experiments themselves are in the exercise cells of the notebook. If you modify this file, restart
the kernel.
"""
import matplotlib.pyplot as plt
import mitsuba as mi
import numpy as np
import sionna.rt
from sionna.rt import (Camera, ITURadioMaterial, InteractionType, PlanarArray, Receiver, Transmitter,
                       load_scene)

__all__ = ["LOGS", "PREVIOUS", "TX_CANYON", "P_TX_DBM", "RX_POINTS", "cam_canyon", "sweep", "sweep_axis",
           "log", "show_log", "db", "watt_to_dbm", "flat_ground", "reflection_coefficient",
           "path_loss_exponent", "make_canyon_scene", "paths_of_rx", "mechanism", "is_outdoor",
           "outdoor_mask", "show_map", "footprints", "plot_coverage"]

LOGS, PREVIOUS = {}, {}                         # the runs of each exercise; the previous run

# Street canyon of Exercises 0 and 3-6
TX_CANYON = [60.0, 0.0, 10.0]                   # small cell on a 10 m pole in the main street
P_TX_DBM = 30.0                                 # transmit power [dBm]
RX_POINTS = {"RX-LoS": [-10.0, 0.0, 1.5],       # main street, line of sight, 70 m from the TX
             "RX-NLoS": [24.0, 25.0, 1.5],      # cross street, behind a building corner
             "RX-corner": [-88.0, -14.0, 1.5],  # just past the west end of the southern buildings
             "RX-shadow": [-88.0, -20.0, 1.5]}  # 6 m deeper in the shadow of the same buildings
cam_canyon = Camera(position=[-5.0, -60.0, 290.0], look_at=[-5.0, -5.0, 0.0])
TYPE_LETTER = {int(InteractionType.SPECULAR): "R", int(InteractionType.DIFFRACTION): "D",
               int(InteractionType.REFRACTION): "T", int(InteractionType.DIFFUSE): "S"}


def sweep(**params):
    # The runs of an experiment: a list given to ONE parameter means one run per value
    lists = [k for k, v in params.items() if isinstance(v, list)]
    if len(lists) > 1:
        raise ValueError("give a list of values to one parameter at a time, not to " + " and ".join(lists))
    if not lists:
        return None, [params]
    return lists[0], [dict(params, **{lists[0]: v}) for v in params[lists[0]]]


def sweep_axis(ax, name, values, ylabel):
    # x axis of a sweep plot: the values of the swept parameter (numbers, or labels)
    numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)
    if not numeric:
        ax.set_xticks(range(len(values)), [str(v) for v in values], rotation=15)
    elif name in ("NUM_RAYS", "CELL_SIZE", "SIGNAL_BANDWIDTH_MHZ", "COHERENCE_BANDWIDTH_MHZ"):
        ax.set_xscale("log")
    ax.set(xlabel=name, ylabel=ylabel)
    return values if numeric else list(range(len(values)))


def log(exercise, row):
    LOGS.setdefault(exercise, []).append(row)


def show_log(exercise):
    '''Print all the runs of an exercise, e.g. show_log("Ex 3").'''
    rows = LOGS.get(exercise, [])
    columns = list(dict.fromkeys(c for row in rows for c in row))
    width = {c: max([len(c)] + [len(row.get(c, "")) for row in rows]) for c in columns}
    print(f"\nLog of {exercise} ({len(rows)} run{'' if len(rows) == 1 else 's'}):")
    print("  #  " + "  ".join(c.rjust(width[c]) for c in columns))
    for i, row in enumerate(rows, 1):
        print(f"{i:3d}  " + "  ".join(row.get(c, "").rjust(width[c]) for c in columns))


def db(x):
    with np.errstate(divide="ignore"):
        return 10*np.log10(x)


def watt_to_dbm(p_w):
    return db(np.asarray(p_w, dtype=float)/1e-3)


def flat_ground(x_min, x_max, y_min, y_max, tile=100.0):
    # Flat ground at z = 0 made of square tiles (two triangles each), as a Mitsuba mesh.
    # (One huge triangle would lose some reflections because of single-precision errors.)
    xs = np.arange(x_min, x_max + tile/2, tile)
    ys = np.arange(y_min, y_max + tile/2, tile)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    vertices = np.stack([X.ravel(), Y.ravel(), np.zeros(X.size)], axis=1)
    ny = len(ys)
    faces = []
    for i in range(len(xs) - 1):
        for j in range(ny - 1):
            v0, v1, v2, v3 = i*ny + j, (i+1)*ny + j, (i+1)*ny + j + 1, i*ny + j + 1
            faces += [[v0, v1, v2], [v0, v2, v3]]
    faces = np.array(faces)
    mesh = mi.Mesh("ground", vertex_count=len(vertices), face_count=len(faces),
                   has_vertex_normals=False, has_vertex_texcoords=False)
    params = mi.traverse(mesh)
    params["vertex_positions"] = mi.Float(vertices.ravel().astype(np.float32))
    params["faces"] = mi.UInt32(faces.ravel().astype(np.uint32))
    params.update()
    return mesh


def reflection_coefficient(theta_i, eta, polarization):
    # Gamma of a flat ground (ITU-R P.2040, as in Sionna): TM for "V" antennas, TE for "H" antennas.
    # theta_i: angle of incidence from the normal [rad]; eta: complex relative permittivity
    cos_i, root = np.cos(theta_i), np.sqrt(eta - np.sin(theta_i)**2)
    if polarization == "V":
        return (eta*cos_i - root)/(eta*cos_i + root)
    return (cos_i - root)/(cos_i + root)


def path_loss_exponent(d, pg_db, d_min, d_max):
    # alpha from a least-squares fit of PG_dB = A - 10 alpha log10(d) over d_min <= d <= d_max
    if d_max < 2*d_min:
        return np.nan
    sel = (d >= d_min) & (d <= d_max)
    return -np.polyfit(np.log10(d[sel]), pg_db[sel], 1)[0]/10


def make_canyon_scene(frequency_hz=3.5e9, buildings="default", scattering=0.0, transmitters=None,
                      receivers=None, tx_power_dbm=P_TX_DBM):
    # simple_street_canyon with isotropic V antennas. buildings: "default" (the materials of the
    # scene) or one ITU material for all buildings; the floor stays concrete. transmitters: list of
    # positions [x, y, z] (default: the small cell); receivers: dictionary name -> position
    scene = load_scene(sionna.rt.scene.simple_street_canyon)
    scene.frequency = frequency_hz
    if buildings != "default":
        material = ITURadioMaterial(f"buildings-{buildings}", buildings, thickness=0.1)
        for name, obj in scene.objects.items():
            if name != "floor":
                obj.radio_material = material
    for name, obj in scene.objects.items():
        if name != "floor":
            obj.radio_material.scattering_coefficient = scattering
    scene.tx_array = PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
    scene.rx_array = PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
    for i, position in enumerate(transmitters or [TX_CANYON]):
        scene.add(Transmitter(name=f"tx{i}", position=[float(c) for c in position],
                              power_dbm=tx_power_dbm, display_radius=3.0))
    for name, position in (receivers or {}).items():
        scene.add(Receiver(name=name, position=position, display_radius=3.0))
    return scene


def paths_of_rx(paths, rx):
    # Valid paths of receiver index `rx` (one transmitter, single antennas): complex baseband
    # coefficients a_i, delays tau_i [s], and interaction strings ("LoS", "R", "R-D", ...)
    a, tau = paths.cir(normalize_delays=False, out_type="numpy")
    a, tau = a[rx, 0, 0, 0, :, 0], tau[rx, 0, :]
    valid = paths.valid.numpy()[rx, 0, :]
    inter = paths.interactions.numpy()[:, rx, 0, :]
    types = ["-".join(TYPE_LETTER[int(t)] for t in inter[:, i] if t != 0) or "LoS"
             for i in range(inter.shape[1])]
    keep = np.flatnonzero(valid)
    return a[keep], tau[keep], [types[i] for i in keep]


def mechanism(interactions):
    # "L" line of sight, "S" with diffuse scattering, "D" with a diffraction, "R" reflections only
    if interactions == "LoS":
        return "L"
    return "S" if "S" in interactions else "D" if "D" in interactions else "R"


def is_outdoor(scene, x, y, z):
    # True if no building covers the point (x, y) at height z (vertical ray cast from above)
    top = float(scene.mi_scene.bbox().max.z) + 10.0
    hit = scene.mi_scene.ray_intersect(mi.Ray3f(mi.Point3f(x, y, top), mi.Vector3f(0.0, 0.0, -1.0)))
    return float(hit.t.numpy()[0]) >= top - z


def outdoor_mask(scene, rm, z=1.5):
    # True for the radio-map cells with no building above them (vertical ray cast from above)
    centers = rm.cell_centers.numpy().reshape(-1, 3)
    z_top = float(scene.mi_scene.bbox().max.z) + 10.0
    origins = mi.Point3f(centers[:, 0], centers[:, 1], np.full(len(centers), z_top, dtype=np.float32))
    hit = scene.mi_scene.ray_intersect(mi.Ray3f(origins, mi.Vector3f(0.0, 0.0, -1.0)))
    return (hit.t.numpy() >= z_top - z).reshape(rm.cell_centers.shape[:2])


def show_map(ax, values_db, rm, outdoor, title, transmitters, vmin=-130, vmax=-30):
    # Top view of a received-power map [dBm]; buildings in grey, cells without signal in white
    centers = rm.cell_centers.numpy()
    half = (centers[0, 1, 0] - centers[0, 0, 0])/2
    extent = [centers[0, 0, 0] - half, centers[0, -1, 0] + half,
              centers[0, 0, 1] - half, centers[-1, 0, 1] + half]
    shown = np.where(np.isfinite(values_db), values_db, np.nan)
    im = ax.imshow(shown, origin="lower", extent=extent, vmin=vmin, vmax=vmax, cmap="viridis")
    ax.imshow(np.where(outdoor, np.nan, 1.0), origin="lower", extent=extent, cmap="Greys",
              vmin=0, vmax=1.6)
    for x, y, _ in transmitters:
        ax.plot(x, y, "r^", ms=8)
    ax.plot([p[0] for p in RX_POINTS.values()], [p[1] for p in RX_POINTS.values()], "mx", ms=6, mew=2)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("x [m]")
    ax.grid(False)
    plt.colorbar(im, ax=ax, shrink=0.8, label="received power P_R [dBm]")


def footprints(scene):
    # Footprint (x0, x1, y0, y1), height and material of every building. A mesh can hold several
    # buildings: its faces are grouped into connected boxes (faces whose bounding boxes touch).
    out = []
    for name, obj in scene.objects.items():
        if name == "floor":
            continue
        params = mi.traverse(obj.mi_mesh)
        v = params["vertex_positions"].numpy().reshape(-1, 3)
        f = params["faces"].numpy().reshape(-1, 3)
        lo, hi = v[f].min(axis=1), v[f].max(axis=1)
        touch = np.all((lo[:, None] <= hi[None] + 0.01) & (lo[None] <= hi[:, None] + 0.01), axis=2)
        label = np.arange(len(f))
        while True:                       # every face takes the smallest label of its neighbours
            new = np.array([label[touch[i]].min() for i in range(len(f))])
            if np.array_equal(new, label):
                break
            label = new
        for k in np.unique(label):
            (x0, y0, _), (x1, y1, z1) = lo[label == k].min(axis=0), hi[label == k].max(axis=0)
            out.append((x0, x1, y0, y1, z1, obj.radio_material.itu_type))
    return out


def plot_coverage(maps, name):
    # Exercises 4-5: one map per run (at most 6) and, for a sweep, the coverage vs the parameter
    shown = maps[:6]
    panels = len(shown) + (name is not None)
    ncols = min(3, panels)
    fig, axes = plt.subplots(-(-panels//ncols), ncols, figsize=(5.4*ncols, 4.4*(-(-panels//ncols))),
                             squeeze=False)
    axes = axes.ravel()
    for ax, m in zip(axes, shown):
        title = (f"{name} = {m['p'][name]}: " if name else "") + f"coverage {m['coverage']:.1f} %"
        show_map(ax, m["prx"], m["rm"], m["outdoor"], title, m["tx"])
    if name is not None:
        ax = axes[len(shown)]
        x = sweep_axis(ax, name, [m["p"][name] for m in maps], "outdoor cells [%]")
        ax.plot(x, [m["coverage"] for m in maps], "o-", label="covered")
        ax.plot(x, [m["reached"] for m in maps], "s--", label="reached by a ray")
        ax.set(ylim=(0, 100), title=f"Coverage vs {name}")
        ax.legend(fontsize=8)
    for ax in axes[panels:]:
        ax.axis("off")
    fig.tight_layout()
    plt.show()
