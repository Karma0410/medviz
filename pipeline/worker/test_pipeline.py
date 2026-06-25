import argparse
import csv
import logging
import random
import time
from collections import defaultdict
from pathlib import Path

from .pipeline import classify, classify_by_ratio, run_segmentation_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
OASIS_DIR   = _HERE / "oasis"
CSV_PATH    = _HERE / "oasis_cross-sectional.csv"
RESULTS_DIR = _HERE / "results"


def _load_ground_truth() -> dict[str, dict]:
    gt = {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = row["ID"].strip()
            def _float(val):
                v = val.strip()
                return float(v) if v not in ("", "N/A") else None
            gt[pid] = {
                "cdr":  _float(row["CDR"]),
                "age":  int(row["Age"]) if row["Age"].strip() else None,
                "sex":  row["M/F"].strip(),
                "mmse": _float(row["MMSE"]),
                "nwbv": _float(row["nWBV"]),
            }
    return gt


def _find_nii_files() -> dict[str, Path]:
    files = {}
    for f in sorted(OASIS_DIR.glob("*.nii.gz")):
        pid = "_".join(f.name.split("_")[:3])
        files[pid] = f
    return files


def _cdr_to_group(cdr) -> str:
    if cdr is None:
        return "Unknown"
    if cdr == 0:
        return "CN"
    if cdr == 0.5:
        return "MCI"
    return "AD"


def run_testsuite(
    n: int = 10,
    seed: int | None = None,
    group_filter: str | None = None,
    output: str | None = None,
) -> list[dict]:
    gt = _load_ground_truth()
    nii = _find_nii_files()

    common = sorted(set(gt) & set(nii))
    logger.info("Patients disponibles (NII + CSV) : %d", len(common))

    if group_filter:
        common = [p for p in common if _cdr_to_group(gt[p]["cdr"]) == group_filter]
        logger.info("Après filtre groupe=%s : %d patients", group_filter, len(common))

    if n and n < len(common):
        rng = random.Random(seed)
        common = sorted(rng.sample(common, n))

    logger.info("Patients à tester : %d\n", len(common))

    results = []

    for i, pid in enumerate(common, 1):
        patient_gt = gt[pid]
        expected   = _cdr_to_group(patient_gt["cdr"])

        logger.info("─── [%d/%d] %s  |  attendu: %-4s  (CDR=%.1g, âge=%s, MMSE=%s)",
                    i, len(common), pid, expected,
                    patient_gt["cdr"] or 0,
                    patient_gt["age"] or "?",
                    patient_gt["mmse"] or "?")

        t0 = time.time()
        try:
            res     = run_segmentation_pipeline(str(nii[pid]))
            elapsed = time.time() - t0

            avg_vol  = (res["left_volume"] + res["right_volume"]) / 2
            brain_vol = res["brain_volume"]
            hippo_ratio_pct = avg_vol / brain_vol * 100 if brain_vol > 0 else None

            predicted_volume = classify(avg_vol, patient_gt["age"]).split(" ")[0]
            predicted_ratio  = classify_by_ratio(hippo_ratio_pct, patient_gt["age"]).split(" ")[0]
            correct_volume   = predicted_volume == expected
            correct_ratio    = predicted_ratio == expected
            avg_dice  = (res["dice_left"] + res["dice_right"]) / 2

            logger.info("    volume: %s %-4s  |  ratio: %s %-4s  vol=%.2f cm³/côté  Dice=%.3f  [%.1fs]",
                        "✓" if correct_volume else "✗", predicted_volume,
                        "✓" if correct_ratio else "✗", predicted_ratio,
                        avg_vol, avg_dice, elapsed)

            results.append({
                "patient_id":    pid,
                "age":           patient_gt["age"],
                "sex":           patient_gt["sex"],
                "mmse":          patient_gt["mmse"],
                "nwbv":          patient_gt["nwbv"],
                "cdr":           patient_gt["cdr"],
                "expected":        expected,
                "predicted_volume": predicted_volume,
                "predicted_ratio":  predicted_ratio,
                "correct_volume":   correct_volume,
                "correct_ratio":    correct_ratio,
                "vol_left_cm3":  round(res["left_volume"],  3),
                "vol_right_cm3": round(res["right_volume"], 3),
                "vol_avg_cm3":   round(avg_vol, 3),
                "brain_volume_cm3": round(brain_vol, 1),
                "hippo_ratio_pct":  round(hippo_ratio_pct, 4) if hippo_ratio_pct is not None else None,
                "asymmetry_pct": round(res["asymmetry_index"], 1),
                "dice_left":     round(res["dice_left"],  3),
                "dice_right":    round(res["dice_right"], 3),
                "iou_left":      round(res["iou_left"],   3),
                "iou_right":     round(res["iou_right"],  3),
                "hd95_left":     round(res["hd95_left"],  3) if res["hd95_left"] == res["hd95_left"] else None,
                "hd95_right":    round(res["hd95_right"], 3) if res["hd95_right"] == res["hd95_right"] else None,
                "runtime_s":     round(elapsed, 1),
                "error":         "",
            })

        except Exception as exc:
            elapsed = time.time() - t0
            logger.error("    ERREUR : %s", exc)
            results.append({
                "patient_id": pid,
                "age": patient_gt["age"],
                "sex": patient_gt["sex"],
                "mmse": patient_gt["mmse"],
                "nwbv": patient_gt["nwbv"],
                "cdr": patient_gt["cdr"],
                "expected": expected,
                "predicted_volume": "ERROR",
                "predicted_ratio": "ERROR",
                "correct_volume": False,
                "correct_ratio": False,
                "vol_left_cm3":  None, "vol_right_cm3": None, "vol_avg_cm3": None,
                "brain_volume_cm3": None, "hippo_ratio_pct": None,
                "asymmetry_pct": None,
                "dice_left": None, "dice_right": None,
                "iou_left": None,  "iou_right": None,
                "hd95_left": None, "hd95_right": None,
                "runtime_s": round(elapsed, 1),
                "error": str(exc),
            })

    _print_summary(results)
    _save_results(results, output)
    return results


def _print_method_section(ok: list[dict], groups: list[str], label: str, pred_key: str, correct_key: str) -> None:
    correct  = [r for r in ok if r[correct_key]]
    accuracy = len(correct) / len(ok) * 100 if ok else 0

    print(f"\n  ── {label} ──")
    print(f"  Précision globale   : {accuracy:.1f}%  ({len(correct)}/{len(ok)})")

    print(f"  {'Groupe':6}  {'n':>4}  {'Acc':>6}")
    print(f"  {'─'*6}  {'─'*4}  {'─'*6}")
    for g in groups:
        grp = [r for r in ok if r["expected"] == g]
        if not grp:
            continue
        g_acc = sum(1 for r in grp if r[correct_key]) / len(grp) * 100
        print(f"  {g:6}  {len(grp):4d}  {g_acc:5.0f}%")

    print("  Matrice de confusion  (lignes=attendu, colonnes=prédit) :")
    header = f"  {'':6}  " + "  ".join(f"{g:>6}" for g in groups)
    print(header)
    for expected in groups:
        row = [r for r in ok if r["expected"] == expected]
        if not row:
            continue
        counts = {g: sum(1 for r in row if r[pred_key] == g) for g in groups}
        line = f"  {expected:6}  " + "  ".join(f"{counts[g]:6d}" for g in groups)
        print(line)


def _print_summary(results: list[dict]) -> None:
    ok     = [r for r in results if not r["error"]]
    errors = [r for r in results if r["error"]]

    avg_dice    = sum((r["dice_left"] + r["dice_right"]) / 2 for r in ok) / len(ok) if ok else 0
    avg_runtime = sum(r["runtime_s"] for r in results) / len(results) if results else 0

    groups = ["CN", "MCI", "AD"]

    print("\n" + "═" * 62)
    print("  RÉSUMÉ TESTSUITE")
    print("═" * 62)
    print(f"  Patients testés     : {len(results)}")
    if errors:
        print(f"  Erreurs             : {len(errors)}")
    print(f"  Dice moyen          : {avg_dice:.3f}")
    print(f"  Temps moyen/patient : {avg_runtime:.1f} s")

    print("\n  ── Qualité de segmentation par groupe ──")
    print(f"  {'Groupe':6}  {'n':>4}  {'Vol moy (cm³/côté)':>20}  {'Dice moy':>9}")
    print(f"  {'─'*6}  {'─'*4}  {'─'*20}  {'─'*9}")
    for g in groups:
        grp = [r for r in ok if r["expected"] == g]
        if not grp:
            continue
        g_vol  = sum(r["vol_avg_cm3"] for r in grp) / len(grp)
        g_dice = sum((r["dice_left"] + r["dice_right"]) / 2 for r in grp) / len(grp)
        print(f"  {g:6}  {len(grp):4d}  {g_vol:20.3f}  {g_dice:9.3f}")

    _print_method_section(ok, groups, "Diagnostic par volume brut", "predicted_volume", "correct_volume")
    _print_method_section(ok, groups, "Diagnostic par ratio hippocampe/cerveau", "predicted_ratio", "correct_ratio")

    print("\n" + "═" * 62 + "\n")


def _save_results(results: list[dict], output: str | None) -> None:
    if not results:
        return
    RESULTS_DIR.mkdir(exist_ok=True)
    path = Path(output) if output else RESULTS_DIR / f"results_{len(results)}patients.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    logger.info("Résultats sauvegardés : %s", path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Testsuite pipeline hippocampe OASIS")
    parser.add_argument("--n",      type=int, default=10,
                        help="Nombre de patients à tester (0 = tous, défaut : 10)")
    parser.add_argument("--seed",   type=int, default=None,
                        help="Graine aléatoire pour reproductibilité")
    parser.add_argument("--group",  choices=["CN", "MCI", "AD"], default=None,
                        help="Restreindre à un groupe clinique")
    parser.add_argument("--output", type=str, default=None,
                        help="Fichier CSV de sortie")
    args = parser.parse_args()

    run_testsuite(
        n=args.n,
        seed=args.seed,
        group_filter=args.group,
        output=args.output,
    )
