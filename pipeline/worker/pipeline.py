import logging
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import SimpleITK as sitk
from scipy.ndimage import (
    binary_closing,
    binary_erosion,
    binary_opening,
    distance_transform_edt,
    gaussian_filter,
    label as connected_components,
    zoom,
)

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ATLAS_DIR = _HERE / "atlas"

ATLAS_L = str(_ATLAS_DIR / "hypocampe" / "HarP-prob_L.nii")
ATLAS_R = str(_ATLAS_DIR / "hypocampe" / "HarP-prob_R.nii")
MNI_TEMPLATE = str(_ATLAS_DIR / "hypocampe" / "mni_icbm152_t1_tal_nlin_asym_09c.nii")
MNI_BRAIN_MASK = str(_ATLAS_DIR / "skull" / "MNI152_T1_1mm_brain_mask.nii.gz")

ATLAS_THRESHOLD = 0.3
GT_THRESHOLD = 0.5
INTENSITY_LOW = 0.20
INTENSITY_HIGH = 0.42
INTENSITY_LOW_RAW = 0.50
INTENSITY_HIGH_RAW = 0.95
ROI_PADDING = 5

_REF_UNDER_75 = (4.30, 3.79)
_REF_75_AND_OVER = (4.04, 3.92)

_REF_RATIO_UNDER_75 = (0.2079, 0.1745)
_REF_RATIO_75_AND_OVER = (0.1984, 0.1907)


def _arr_to_sitk(data: np.ndarray, zooms: list[float]) -> sitk.Image:
    img = sitk.GetImageFromArray(data.T.astype(np.float32))
    img.SetSpacing([float(z) for z in zooms])
    return img


def _sitk_to_arr(sitk_img: sitk.Image) -> np.ndarray:
    return sitk.GetArrayFromImage(sitk_img).T.astype(np.float32)


def _load(path: str) -> nib.Nifti1Image:
    img = nib.squeeze_image(nib.load(path))
    logger.debug("  [load] %s → shape=%s zooms=%s", Path(path).name, img.shape,
                 img.header.get_zooms()[:3])
    return img


def _check_atlas_files() -> None:
    for p in [ATLAS_L, ATLAS_R, MNI_TEMPLATE, MNI_BRAIN_MASK]:
        if not Path(p).exists():
            raise FileNotFoundError(f"Fichier atlas introuvable : {p}")


def _affine_register(fixed: sitk.Image, moving: sitk.Image) -> sitk.Transform:
    initial_tx = sitk.CenteredTransformInitializer(
        fixed, moving,
        sitk.AffineTransform(3),
        sitk.CenteredTransformInitializerFilter.GEOMETRY,
    )

    reg = sitk.ImageRegistrationMethod()
    reg.SetMetricAsMattesMutualInformation(numberOfHistogramBins=50)
    reg.SetMetricSamplingStrategy(reg.RANDOM)
    reg.SetMetricSamplingPercentage(0.1)
    reg.SetInterpolator(sitk.sitkLinear)
    reg.SetOptimizerAsGradientDescent(
        learningRate=1.0,
        numberOfIterations=200,
        convergenceMinimumValue=1e-6,
        convergenceWindowSize=10,
    )
    reg.SetOptimizerScalesFromPhysicalShift()
    reg.SetInitialTransform(initial_tx, inPlace=False)
    reg.SetShrinkFactorsPerLevel([4, 2, 1])
    reg.SetSmoothingSigmasPerLevel([2.0, 1.0, 0.0])
    reg.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()

    return reg.Execute(fixed, moving)


def _atlas_skull_strip(data: np.ndarray, zooms: list[float]) -> np.ndarray:
    from nibabel.processing import resample_from_to as nib_resample_from_to

    mni_nib = nib.squeeze_image(nib.load(MNI_TEMPLATE))
    mask_nib = nib.squeeze_image(nib.load(MNI_BRAIN_MASK))
    mask_on_mni = nib_resample_from_to(mask_nib, mni_nib, order=0, cval=0.0)

    mni_data = mni_nib.get_fdata(dtype=np.float32)
    mni_zooms = [float(v) for v in mni_nib.header.get_zooms()[:3]]
    mni_norm = (mni_data - mni_data.min()) / (mni_data.max() - mni_data.min() + 1e-8)
    patient_norm = (data - data.min()) / (data.max() - data.min() + 1e-8)

    fixed = _arr_to_sitk(patient_norm, zooms)
    moving = _arr_to_sitk(mni_norm, mni_zooms)
    moving_mask = _arr_to_sitk(mask_on_mni.get_fdata(dtype=np.float32), mni_zooms)

    transform = _affine_register(fixed, moving)

    resampled_mask = sitk.Resample(
        moving_mask, fixed, transform,
        sitk.sitkNearestNeighbor, 0.0, moving_mask.GetPixelID(),
    )
    return _sitk_to_arr(resampled_mask) > 0.5


_N4_SHRINK_FACTOR = 4


def _n4_correction(sitk_img: sitk.Image, mask: sitk.Image) -> sitk.Image:
    img_f32 = sitk.Cast(sitk_img, sitk.sitkFloat32)

    shrink = [_N4_SHRINK_FACTOR] * img_f32.GetDimension()
    img_shrunk = sitk.Shrink(img_f32, shrink)
    mask_shrunk = sitk.Shrink(mask, shrink)

    corrector = sitk.N4BiasFieldCorrectionImageFilter()
    corrector.SetMaximumNumberOfIterations([50, 50, 30, 20])
    corrector.Execute(img_shrunk, mask_shrunk)

    log_bias_field = corrector.GetLogBiasFieldAsImage(img_f32)
    return img_f32 / sitk.Exp(log_bias_field)


def _normalize(data: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = np.zeros_like(data, dtype=np.float32)
    brain_vals = data[mask]
    ptp = brain_vals.max() - brain_vals.min()
    if ptp == 0:
        return out
    out[mask] = (brain_vals - brain_vals.min()) / ptp
    return out


def preprocess(patient_nib: nib.Nifti1Image, already_preprocessed: bool = False) -> tuple[np.ndarray, np.ndarray]:
    data = patient_nib.get_fdata(dtype=np.float32)
    zooms = [float(v) for v in patient_nib.header.get_zooms()[:3]]

    if already_preprocessed:
        logger.info("    skull stripping : skippé (déjà appliqué) — masque = data > 0")
        brain_mask = data > 1e-6
        logger.info("    N4 : skippé — normalisation [0,1] conservée")
        patient_norm = _normalize(data, brain_mask)
    else:
        logger.info("    skull stripping (recalage vers template MNI)…")
        brain_mask = _atlas_skull_strip(data, zooms)
        data_stripped = data * brain_mask
        logger.info("    correction N4…")
        sitk_img = _arr_to_sitk(data_stripped, zooms)
        sitk_mask = sitk.Cast(_arr_to_sitk(brain_mask.astype(np.float32), zooms) > 0.5,
                              sitk.sitkUInt8)
        sitk_corrected = _n4_correction(sitk_img, sitk_mask)
        corrected = _sitk_to_arr(sitk_corrected)
        logger.info("    normalisation [0, 1]…")
        patient_norm = _normalize(corrected, brain_mask)

    return patient_norm, brain_mask


_MNI_2MM_SHAPE = (91, 109, 91)
_MNI_2MM_VOXEL = 2.0


def _is_mni_2mm(shape: tuple, zooms: list[float]) -> bool:
    return tuple(shape[:3]) == _MNI_2MM_SHAPE and all(
        abs(z - _MNI_2MM_VOXEL) < 0.05 for z in zooms[:3]
    )


def register_to_mni(
    patient_norm: np.ndarray,
    patient_nib: nib.Nifti1Image,
    atlas_ref_nib: nib.Nifti1Image,
    mni_nib: nib.Nifti1Image,
) -> np.ndarray:
    from nibabel.processing import resample_from_to as nib_resample_from_to

    patient_zooms = [float(v) for v in patient_nib.header.get_zooms()[:3]]

    if _is_mni_2mm(patient_norm.shape, patient_zooms):
        logger.info("  patient en MNI 2mm FSL → rééchantillonnage via affines NIfTI")
        patient_norm_nib = nib.Nifti1Image(patient_norm, patient_nib.affine)
        resampled_nib = nib_resample_from_to(patient_norm_nib, atlas_ref_nib,
                                              order=1, cval=0.0)
        return resampled_nib.get_fdata(dtype=np.float32)

    mni_data = mni_nib.get_fdata(dtype=np.float32)
    mni_norm = (mni_data - mni_data.min()) / (mni_data.max() - mni_data.min() + 1e-8)
    mni_zooms = [float(v) for v in mni_nib.header.get_zooms()[:3]]

    fixed = _arr_to_sitk(mni_norm, mni_zooms)
    moving = _arr_to_sitk(patient_norm, patient_zooms)

    transform = _affine_register(fixed, moving)

    resampled = sitk.Resample(
        moving, fixed, transform,
        sitk.sitkLinear, 0.0, moving.GetPixelID(),
    )
    return _sitk_to_arr(resampled)


def apply_atlas(
    patient_registered: np.ndarray,
    atlas_data: np.ndarray,
    threshold: float = ATLAS_THRESHOLD,
    padding: int = ROI_PADDING,
) -> tuple[np.ndarray, np.ndarray, tuple]:
    atlas_mask = atlas_data >= threshold

    if patient_registered.shape != atlas_mask.shape:
        logger.warning("  shape mismatch patient %s vs atlas %s — zoom correctif",
                       patient_registered.shape, atlas_mask.shape)
        factors = [atlas_mask.shape[i] / patient_registered.shape[i] for i in range(3)]
        patient_registered = zoom(patient_registered, factors, order=1)

    coords = np.where(atlas_mask)
    if coords[0].size == 0:
        raise ValueError("Masque atlas vide après seuillage — vérifier le fichier atlas.")

    mins = [max(0, c.min() - padding) for c in coords]
    maxs = [min(atlas_mask.shape[i], c.max() + padding + 1) for i, c in enumerate(coords)]
    slices = tuple(slice(mins[i], maxs[i]) for i in range(3))

    return patient_registered[slices], atlas_mask[slices], slices


def fine_segment(
    roi_data: np.ndarray,
    roi_atlas_mask: np.ndarray,
    low: float = INTENSITY_LOW,
    high: float = INTENSITY_HIGH,
) -> np.ndarray:
    smoothed = gaussian_filter(roi_data.astype(np.float32), sigma=0.5)

    masked_vals = smoothed[roi_atlas_mask]
    if masked_vals.size == 0:
        return np.zeros_like(roi_atlas_mask, dtype=np.uint8)

    logger.debug("    intensités ROI : min=%.3f  médiane=%.3f  max=%.3f",
                 float(masked_vals.min()), float(np.median(masked_vals)),
                 float(masked_vals.max()))

    intensity_mask = (smoothed >= low) & (smoothed <= high)
    combined = intensity_mask & roi_atlas_mask
    opened = binary_opening(combined, iterations=1)
    closed = binary_closing(opened, iterations=2)

    labeled, n = connected_components(closed)
    if n == 0:
        return closed.astype(np.uint8)
    sizes = [(labeled == k).sum() for k in range(1, n + 1)]
    return (labeled == (np.argmax(sizes) + 1)).astype(np.uint8)


def compute_volume_cm3(mask: np.ndarray, voxel_zooms: tuple) -> float:
    return int(mask.sum()) * float(np.prod(voxel_zooms)) / 1000.0


def asymmetry_index(vol_l: float, vol_r: float) -> float:
    total = vol_l + vol_r
    return abs(vol_l - vol_r) / total * 100 if total > 0 else 0.0


def classify(volume_cm3: float, age: int | None = None) -> str:
    cn_min, mci_min = _REF_75_AND_OVER if (age is not None and age >= 75) else _REF_UNDER_75
    if volume_cm3 >= cn_min:
        return "CN (Cognitively Normal)"
    if volume_cm3 >= mci_min:
        return "MCI (Mild Cognitive Impairment)"
    return "AD (Alzheimer's Disease)"


def classify_by_ratio(hippo_ratio_pct: float, age: int | None = None) -> str:
    cn_min, mci_min = (
        _REF_RATIO_75_AND_OVER if (age is not None and age >= 75) else _REF_RATIO_UNDER_75
    )
    if hippo_ratio_pct >= cn_min:
        return "CN (Cognitively Normal)"
    if hippo_ratio_pct >= mci_min:
        return "MCI (Mild Cognitive Impairment)"
    return "AD (Alzheimer's Disease)"


def dice_score(pred: np.ndarray, ref: np.ndarray) -> float:
    pred_b = pred.astype(bool)
    ref_b = ref.astype(bool)
    inter = (pred_b & ref_b).sum()
    return float(2 * inter / (pred_b.sum() + ref_b.sum() + 1e-8))


def iou_score(pred: np.ndarray, ref: np.ndarray) -> float:
    pred_b = pred.astype(bool)
    ref_b = ref.astype(bool)
    inter = (pred_b & ref_b).sum()
    union = (pred_b | ref_b).sum()
    return float(inter / (union + 1e-8))


def hausdorff_distance_95(pred: np.ndarray, ref: np.ndarray, voxel_zooms: tuple) -> float:
    pred_b = pred.astype(bool)
    ref_b = ref.astype(bool)
    if pred_b.sum() == 0 or ref_b.sum() == 0:
        return float("nan")

    pred_surface = pred_b & ~binary_erosion(pred_b)
    ref_surface = ref_b & ~binary_erosion(ref_b)

    dt_from_ref = distance_transform_edt(~ref_surface, sampling=voxel_zooms)
    dt_from_pred = distance_transform_edt(~pred_surface, sampling=voxel_zooms)

    distances = np.concatenate([dt_from_ref[pred_surface], dt_from_pred[ref_surface]])
    return float(np.percentile(distances, 95))


def run_segmentation_pipeline(
    mri_path: str,
    already_preprocessed: bool | None = None,
) -> dict:
    _check_atlas_files()

    logger.info("[1/7] Chargement des fichiers NIfTI")
    patient_nib = _load(mri_path)
    atlas_L_nib = _load(ATLAS_L)
    atlas_R_nib = _load(ATLAS_R)
    mni_nib = _load(MNI_TEMPLATE)

    patient_zooms = [float(v) for v in patient_nib.header.get_zooms()[:3]]
    raw = patient_nib.get_fdata(dtype=np.float32)
    logger.info(
        "  shape=%s  voxel=%.2f×%.2f×%.2f mm  intensités=[%.0f, %.0f]",
        patient_nib.shape, *patient_zooms, raw.min(), raw.max(),
    )

    logger.info("[2/7] Prétraitement")
    if already_preprocessed is None:
        already_preprocessed = "normalised" in Path(mri_path).name
    if already_preprocessed:
        logger.info("  fichier déjà prétraité (skull-stripping + N4) → étapes skippées")
    else:
        logger.info("  IRM brute détectée → skull-stripping + N4 + normalisation complets")
    patient_norm, brain_mask = preprocess(patient_nib, already_preprocessed)
    brain_volume_cm3 = compute_volume_cm3(brain_mask, tuple(patient_zooms))
    logger.info("  volume cérébral total : %.1f cm³", brain_volume_cm3)

    logger.info("[3/7] Recalage affine → espace MNI  (quelques minutes…)")
    patient_registered = register_to_mni(patient_norm, patient_nib, atlas_L_nib, mni_nib)
    logger.info("  shape recalée : %s", patient_registered.shape)

    logger.info("[4/7] Application de l'atlas HarP")
    atlas_L_data = atlas_L_nib.get_fdata(dtype=np.float32)
    atlas_R_data = atlas_R_nib.get_fdata(dtype=np.float32)
    atlas_zooms = tuple(float(v) for v in atlas_L_nib.header.get_zooms()[:3])

    roi_L, atlas_mask_L, slices_L = apply_atlas(patient_registered, atlas_L_data)
    roi_R, atlas_mask_R, slices_R = apply_atlas(patient_registered, atlas_R_data)
    logger.info("  ROI gauche : %s  ROI droite : %s", roi_L.shape, roi_R.shape)

    logger.info("[5/7] Segmentation fine dans les ROIs")
    seg_low, seg_high = (
        (INTENSITY_LOW, INTENSITY_HIGH) if already_preprocessed
        else (INTENSITY_LOW_RAW, INTENSITY_HIGH_RAW)
    )
    mask_L = fine_segment(roi_L, atlas_mask_L, seg_low, seg_high)
    mask_R = fine_segment(roi_R, atlas_mask_R, seg_low, seg_high)

    logger.info("[6/7] Volumétrie")
    vol_L = compute_volume_cm3(mask_L, atlas_zooms)
    vol_R = compute_volume_cm3(mask_R, atlas_zooms)
    vol_total = vol_L + vol_R
    ai = asymmetry_index(vol_L, vol_R)

    ratio_L = vol_L / brain_volume_cm3 * 100 if brain_volume_cm3 > 0 else 0.0
    ratio_R = vol_R / brain_volume_cm3 * 100 if brain_volume_cm3 > 0 else 0.0

    logger.info("  Hippocampe gauche : %.3f cm³  (%.2f %% du cerveau)", vol_L, ratio_L)
    logger.info("  Hippocampe droit  : %.3f cm³  (%.2f %% du cerveau)", vol_R, ratio_R)
    logger.info("  Volume total      : %.3f cm³", vol_total)
    logger.info("  Index asymétrie   : %.1f %%", ai)

    logger.info("[7/7] Évaluation  (Dice + IoU + HD95)")
    gt_L = (atlas_L_data[slices_L] >= GT_THRESHOLD).astype(np.uint8)
    gt_R = (atlas_R_data[slices_R] >= GT_THRESHOLD).astype(np.uint8)

    d_L = dice_score(mask_L, gt_L)
    d_R = dice_score(mask_R, gt_R)
    i_L = iou_score(mask_L, gt_L)
    i_R = iou_score(mask_R, gt_R)
    hd95_L = hausdorff_distance_95(mask_L, gt_L, atlas_zooms)
    hd95_R = hausdorff_distance_95(mask_R, gt_R, atlas_zooms)

    logger.info("  Gauche : Dice=%.3f  IoU=%.3f  HD95=%.2f mm", d_L, i_L, hd95_L)
    logger.info("  Droit  : Dice=%.3f  IoU=%.3f  HD95=%.2f mm", d_R, i_R, hd95_R)

    asym_note = f"  ⚠ Asymétrie significative : {ai:.1f} %" if ai > 10.0 else ""
    status_text = (
        f"Hippocampe gauche : {vol_L:.3f} cm³  ({ratio_L:.2f} % du cerveau)\n"
        f"Hippocampe droit  : {vol_R:.3f} cm³  ({ratio_R:.2f} % du cerveau)\n"
        f"Volume total      : {vol_total:.3f} cm³{asym_note}\n"
        f"Dice : G={d_L:.3f}  D={d_R:.3f}  |  IoU : G={i_L:.3f}  D={i_R:.3f}"
    )

    return {
        "left_volume": float(vol_L),
        "right_volume": float(vol_R),
        "total_volume": float(vol_total),
        "brain_volume": float(brain_volume_cm3),
        "hippo_ratio_left": float(ratio_L),
        "hippo_ratio_right": float(ratio_R),
        "asymmetry_index": float(ai),
        "dice_left": float(d_L),
        "dice_right": float(d_R),
        "iou_left": float(i_L),
        "iou_right": float(i_R),
        "hd95_left": float(hd95_L),
        "hd95_right": float(hd95_R),
        "status_text": status_text,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    if len(sys.argv) != 2:
        print("Usage : python pipeline.py <patient.nii>")
        sys.exit(1)

    results = run_segmentation_pipeline(sys.argv[1])
    print("\n" + "═" * 55)
    print("  RÉSULTATS DE SEGMENTATION HIPPOCAMPIQUE")
    print("═" * 55)
    print(results["status_text"])
    print("═" * 55)