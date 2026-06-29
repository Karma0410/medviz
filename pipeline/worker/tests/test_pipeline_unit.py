import numpy as np
import pytest

import worker.pipeline as m

# -------------------------
# Helpers fixtures
# -------------------------


@pytest.fixture
def small_volume():
    return np.zeros((10, 10, 10), dtype=np.float32)


@pytest.fixture
def binary_mask():
    mask = np.zeros((10, 10, 10), dtype=np.uint8)
    mask[2:5, 2:5, 2:5] = 1
    return mask


# -------------------------
# compute_volume_cm3
# -------------------------


def test_compute_volume_cm3_simple():
    mask = np.ones((2, 2, 2), dtype=np.uint8)
    zooms = (1.0, 1.0, 1.0)

    vol = m.compute_volume_cm3(mask, zooms)

    # 8 voxels * 1 mm³ = 8 mm³ = 0.008 cm³
    assert vol == pytest.approx(0.008)


# -------------------------
# asymmetry_index
# -------------------------


def test_asymmetry_index():
    assert m.asymmetry_index(1.0, 1.0) == 0.0
    assert m.asymmetry_index(2.0, 0.0) == 100.0
    assert m.asymmetry_index(2.0, 1.0) == pytest.approx(33.3333, rel=1e-3)


# -------------------------
# dice_score / iou
# -------------------------


def test_dice_iou_perfect_match(binary_mask):
    pred = binary_mask.copy()
    ref = binary_mask.copy()

    assert m.dice_score(pred, ref) == pytest.approx(1.0, rel=1e-6)
    assert m.iou_score(pred, ref) == pytest.approx(1.0, rel=1e-6)


def test_dice_iou_empty():
    pred = np.zeros((5, 5, 5))
    ref = np.zeros((5, 5, 5))

    assert m.dice_score(pred, ref) == pytest.approx(0.0)
    assert m.iou_score(pred, ref) == pytest.approx(0.0)


# -------------------------
# classify / classify_by_ratio
# -------------------------


def test_classify_age_thresholds():
    assert m.classify(4.5, age=80).startswith("CN")
    assert m.classify(3.9, age=80).startswith("MCI") or m.classify(
        3.9, age=80
    ).startswith("AD")


def test_classify_by_ratio():
    assert m.classify_by_ratio(0.25, age=80).startswith("CN")
    assert m.classify_by_ratio(0.10, age=80).startswith("AD")


# -------------------------
# normalize (pure logic)
# -------------------------


def test_normalize():
    data = np.array([[[0, 1], [2, 3]]], dtype=np.float32)
    mask = data > 0

    out = m._normalize(data, mask)

    assert out.shape == data.shape
    assert out.min() >= 0.0
    assert out.max() <= 1.0


def test_normalize_zero_range():
    data = np.ones((3, 3, 3), dtype=np.float32)
    mask = np.ones_like(data, dtype=bool)

    out = m._normalize(data, mask)

    assert np.all(out == 0)


# -------------------------
# fine_segment (core logic)
# -------------------------


def test_fine_segment_basic():
    data = np.random.rand(20, 20, 20).astype(np.float32)
    mask = data > 0.5

    seg = m.fine_segment(data, mask, low=0.2, high=0.9)

    assert seg.shape == mask.shape
    assert seg.dtype == np.uint8


def test_fine_segment_empty_mask():
    data = np.random.rand(10, 10, 10).astype(np.float32)
    mask = np.zeros_like(data, dtype=bool)

    seg = m.fine_segment(data, mask)

    assert np.all(seg == 0)


# -------------------------
# apply_atlas
# -------------------------


def test_apply_atlas_simple():
    patient = np.random.rand(10, 10, 10).astype(np.float32)
    atlas = np.zeros((10, 10, 10), dtype=np.float32)

    atlas[2:6, 2:6, 2:6] = 1.0

    roi, atlas_mask, sl = m.apply_atlas(patient, atlas, threshold=0.5)

    assert roi.shape == atlas_mask.shape
    assert isinstance(sl, tuple)
    assert len(sl) == 3


def test_apply_atlas_empty_error():
    patient = np.random.rand(10, 10, 10).astype(np.float32)
    atlas = np.zeros((10, 10, 10), dtype=np.float32)

    with pytest.raises(ValueError):
        m.apply_atlas(patient, atlas, threshold=0.5)


# -------------------------
# hausdorff (robust test only shape/edge cases)
# -------------------------


def test_hausdorff_empty():
    pred = np.zeros((5, 5, 5), dtype=np.uint8)
    ref = np.zeros((5, 5, 5), dtype=np.uint8)

    out = m.hausdorff_distance_95(pred, ref, (1.0, 1.0, 1.0))

    assert np.isnan(out)
